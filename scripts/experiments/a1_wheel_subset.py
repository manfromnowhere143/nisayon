"""Fail-closed, network-free helpers for a scoped A1 wheel subset.

These helpers plan and verify byte ranges after a caller has separately acquired a ZIP
central directory under a prospectively frozen network contract. They never perform a
request and never treat a publisher-declared whole-wheel digest as locally verified.
Synthetic conformance tests exercise this module; passing them is not runtime evidence.
"""

from __future__ import annotations

import hashlib
import os
import stat
import struct
import zipfile
import zlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

EOCD_SIGNATURE = b"PK\x05\x06"
CENTRAL_SIGNATURE = b"PK\x01\x02"
LOCAL_SIGNATURE = b"PK\x03\x04"
EOCD = struct.Struct("<4s4H2LH")
CENTRAL = struct.Struct("<4s6H3L5H2L")
LOCAL = struct.Struct("<4s5H3L2H")
MAX_EOCD_BYTES = EOCD.size + 65_535
ASSET_PREFIX = "robosuite/models/assets/"
DIST_INFO_PREFIX = "robosuite-1.5.1.dist-info/"
METADATA_MEMBER = f"{DIST_INFO_PREFIX}METADATA"
SUPPORTED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class SubsetError(RuntimeError):
    """The candidate archive or subset plan is unsafe or internally inconsistent."""


class BudgetExceeded(SubsetError):
    """The immutable byte budget cannot contain the planned responses."""

    def __init__(self, *, required: int, ceiling: int):
        super().__init__(f"planned response bytes exceed ceiling: {required} > {ceiling}")
        self.required = required
        self.ceiling = ceiling


@dataclass(frozen=True, order=True)
class ByteRange:
    """An inclusive byte range."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise SubsetError(f"invalid byte range {self.start}-{self.end}")

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    def as_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "bytes": self.length}


@dataclass(frozen=True)
class ZipLayout:
    archive_bytes: int
    central_offset: int
    central_bytes: int
    entries: int
    eocd_offset: int
    eocd_bytes: int


@dataclass(frozen=True)
class ZipMember:
    name: str
    flag_bits: int
    compression: int
    crc32: int
    compressed_bytes: int
    uncompressed_bytes: int
    local_offset: int
    external_attr: int

    @property
    def is_directory(self) -> bool:
        return self.name.endswith("/")

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "flag_bits": self.flag_bits,
            "compression": self.compression,
            "crc32": f"{self.crc32:08x}",
            "compressed_bytes": self.compressed_bytes,
            "uncompressed_bytes": self.uncompressed_bytes,
            "local_offset": self.local_offset,
            "external_attr": self.external_attr,
        }


def _safe_member_name(name: str) -> None:
    if not name or "\x00" in name or "\\" in name or name.startswith("/"):
        raise SubsetError(f"unsafe ZIP member name: {name!r}")
    parts = name.rstrip("/").split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise SubsetError(f"unsafe ZIP member name: {name!r}")


def parse_eocd(*, tail: bytes, tail_start: int, archive_bytes: int) -> ZipLayout:
    """Parse the terminal EOCD from a byte suffix and reject ZIP64 or split archives.

    A caller may deliberately fetch a suffix larger than the classic EOCD search window
    so that the same response also contains the central directory. Only the terminal
    ``MAX_EOCD_BYTES`` are searched for the EOCD signature; earlier signature-like bytes
    cannot become candidates.
    """

    if tail_start < 0 or archive_bytes < 0 or tail_start + len(tail) != archive_bytes:
        raise SubsetError("EOCD input is not an exact suffix of the declared archive")
    if len(tail) > archive_bytes:
        raise SubsetError("EOCD suffix exceeds the declared archive")

    search_start = max(0, len(tail) - MAX_EOCD_BYTES)
    candidate = tail.rfind(EOCD_SIGNATURE, search_start)
    while candidate >= search_start:
        if candidate + EOCD.size <= len(tail):
            fields = EOCD.unpack_from(tail, candidate)
            comment_bytes = fields[-1]
            if candidate + EOCD.size + comment_bytes == len(tail):
                break
        candidate = tail.rfind(EOCD_SIGNATURE, search_start, candidate)
    else:
        raise SubsetError("terminal ZIP EOCD was not found in the supplied suffix")

    (
        _signature,
        disk_number,
        central_disk,
        entries_on_disk,
        entries_total,
        central_bytes,
        central_offset,
        comment_bytes,
    ) = fields
    if disk_number != 0 or central_disk != 0 or entries_on_disk != entries_total:
        raise SubsetError("split or multi-disk ZIP archives are unsupported")
    if entries_total == 0xFFFF or central_bytes == 0xFFFFFFFF or central_offset == 0xFFFFFFFF:
        raise SubsetError("ZIP64 archives require a separately frozen parser")

    eocd_offset = tail_start + candidate
    eocd_bytes = EOCD.size + comment_bytes
    if central_offset + central_bytes != eocd_offset:
        raise SubsetError("central directory is not contiguous with the terminal EOCD")
    if central_offset < 0 or central_offset + central_bytes > archive_bytes:
        raise SubsetError("central directory lies outside the declared archive")
    return ZipLayout(
        archive_bytes=archive_bytes,
        central_offset=central_offset,
        central_bytes=central_bytes,
        entries=entries_total,
        eocd_offset=eocd_offset,
        eocd_bytes=eocd_bytes,
    )


def central_directory_from_suffix(*, suffix: bytes, suffix_start: int, layout: ZipLayout) -> bytes:
    """Return exact central-directory bytes only when the retained suffix contains them."""

    if suffix_start < 0 or suffix_start + len(suffix) != layout.archive_bytes:
        raise SubsetError("central-directory input is not an exact archive suffix")
    if layout.central_offset < suffix_start:
        missing = suffix_start - layout.central_offset
        raise SubsetError(
            "central directory begins before supplied suffix: "
            f"need {missing} earlier bytes or a separately authorized exact range"
        )
    relative_start = layout.central_offset - suffix_start
    relative_end = relative_start + layout.central_bytes
    if relative_end > len(suffix):
        raise SubsetError("central directory ends outside the supplied suffix")
    central_directory = suffix[relative_start:relative_end]
    if len(central_directory) != layout.central_bytes:
        raise SubsetError("central-directory slice length differs from the EOCD declaration")
    return central_directory


def central_directory_from_fragments(
    *, layout: ZipLayout, fragments: Iterable[tuple[ByteRange, bytes]]
) -> bytes:
    """Assemble the exact directory from non-overlapping retained archive fragments."""

    target = ByteRange(layout.central_offset, layout.eocd_offset - 1)
    pieces: list[tuple[ByteRange, bytes]] = []
    for byte_range, body in sorted(fragments, key=lambda item: item[0]):
        if byte_range.end >= layout.archive_bytes:
            raise SubsetError("central-directory fragment extends beyond the archive")
        if len(body) != byte_range.length:
            raise SubsetError("central-directory fragment length differs from its range")
        start = max(byte_range.start, target.start)
        end = min(byte_range.end, target.end)
        if start > end:
            continue
        body_start = start - byte_range.start
        body_end = body_start + end - start + 1
        pieces.append((ByteRange(start, end), body[body_start:body_end]))
    if not pieces:
        raise SubsetError("no retained fragment intersects the central directory")

    cursor = target.start
    assembled = bytearray()
    for byte_range, body in pieces:
        if byte_range.start < cursor:
            raise SubsetError("retained central-directory fragments overlap")
        if byte_range.start > cursor:
            raise SubsetError(
                f"retained central-directory fragments have a gap: {cursor}-{byte_range.start - 1}"
            )
        assembled.extend(body)
        cursor = byte_range.end + 1
    if cursor <= target.end:
        raise SubsetError(
            f"retained central-directory fragments have a terminal gap: {cursor}-{target.end}"
        )
    central_directory = bytes(assembled)
    if len(central_directory) != layout.central_bytes:
        raise SubsetError("assembled central-directory length differs from the EOCD declaration")
    return central_directory


def parse_central_directory(data: bytes, layout: ZipLayout) -> tuple[ZipMember, ...]:
    """Parse an exact classic-ZIP central directory into a validated immutable table."""

    if len(data) != layout.central_bytes:
        raise SubsetError(
            f"central-directory length differs: {len(data)} != {layout.central_bytes}"
        )
    members: list[ZipMember] = []
    names: set[str] = set()
    offsets: set[int] = set()
    cursor = 0
    for _index in range(layout.entries):
        if cursor + CENTRAL.size > len(data):
            raise SubsetError("central directory ended inside a member header")
        fields = CENTRAL.unpack_from(data, cursor)
        if fields[0] != CENTRAL_SIGNATURE:
            raise SubsetError(f"invalid central-directory signature at byte {cursor}")
        (
            _signature,
            _version_made,
            _version_needed,
            flag_bits,
            compression,
            _modified_time,
            _modified_date,
            crc32,
            compressed_bytes,
            uncompressed_bytes,
            name_bytes,
            extra_bytes,
            comment_bytes,
            disk_start,
            _internal_attr,
            external_attr,
            local_offset,
        ) = fields
        end = cursor + CENTRAL.size + name_bytes + extra_bytes + comment_bytes
        if end > len(data):
            raise SubsetError("central directory ended inside variable member metadata")
        raw_name = data[cursor + CENTRAL.size : cursor + CENTRAL.size + name_bytes]
        encoding = "utf-8" if flag_bits & 0x800 else "cp437"
        try:
            name = raw_name.decode(encoding)
        except UnicodeDecodeError as error:
            raise SubsetError("ZIP member name is not valid in its declared encoding") from error
        _safe_member_name(name)
        if name in names:
            raise SubsetError(f"duplicate ZIP member name: {name}")
        if local_offset in offsets:
            raise SubsetError(f"duplicate local-header offset: {local_offset}")
        if flag_bits & 0x1:
            raise SubsetError(f"encrypted ZIP member is unsupported: {name}")
        if compression not in SUPPORTED_COMPRESSION:
            raise SubsetError(f"unsupported compression method {compression}: {name}")
        if disk_start != 0:
            raise SubsetError(f"member starts on another disk: {name}")
        if compressed_bytes == 0xFFFFFFFF or uncompressed_bytes == 0xFFFFFFFF:
            raise SubsetError(f"ZIP64 member is unsupported: {name}")
        if local_offset >= layout.central_offset:
            raise SubsetError(f"local header lies beyond file data: {name}")
        unix_mode = external_attr >> 16
        if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
            raise SubsetError(f"symbolic-link ZIP member is unsupported: {name}")
        names.add(name)
        offsets.add(local_offset)
        members.append(
            ZipMember(
                name=name,
                flag_bits=flag_bits,
                compression=compression,
                crc32=crc32,
                compressed_bytes=compressed_bytes,
                uncompressed_bytes=uncompressed_bytes,
                local_offset=local_offset,
                external_attr=external_attr,
            )
        )
        cursor = end
    if cursor != len(data):
        raise SubsetError("central directory has trailing or unparsed bytes")
    return tuple(members)


def select_members(
    members: Iterable[ZipMember], *, referenced_asset_members: Iterable[str]
) -> tuple[ZipMember, ...]:
    """Apply the frozen non-asset, XML/JSON, and explicit-asset selection rule."""

    explicit = set(referenced_asset_members)
    for name in explicit:
        _safe_member_name(name)
        if not name.startswith(ASSET_PREFIX):
            raise SubsetError(f"explicit asset is outside {ASSET_PREFIX}: {name}")
    available = {member.name for member in members}
    missing = sorted(explicit - available)
    if missing:
        raise SubsetError(f"referenced asset members are absent: {missing}")
    selected = [
        member
        for member in members
        if not member.name.startswith(ASSET_PREFIX)
        or member.name.endswith((".xml", ".json"))
        or member.name in explicit
    ]
    if not selected:
        raise SubsetError("selection produced no members")
    return tuple(sorted(selected, key=lambda member: member.name))


def plan_rights_range(
    *, members: Iterable[ZipMember], central_offset: int
) -> tuple[tuple[ZipMember, ...], ByteRange]:
    """Select frozen terms members and their smallest continuous local-data range."""

    member_table = tuple(members)
    by_name = {member.name: member for member in member_table}
    metadata = by_name.get(METADATA_MEMBER)
    if metadata is None or metadata.is_directory:
        raise SubsetError(f"required metadata member is absent: {METADATA_MEMBER}")
    dist_licenses = []
    package_licenses = []
    for member in member_table:
        if member.is_directory:
            continue
        if member.name.startswith(DIST_INFO_PREFIX):
            relative_name = member.name.removeprefix(DIST_INFO_PREFIX)
            if relative_name.upper().startswith("LICENSE") or relative_name.startswith("licenses/"):
                dist_licenses.append(member)
            continue
        if member.name.startswith("robosuite/"):
            relative_name = member.name.removeprefix("robosuite/")
            if "/" not in relative_name and relative_name.upper().startswith("LICENSE"):
                package_licenses.append(member)
    dist_licenses.sort(key=lambda member: member.name)
    package_licenses.sort(key=lambda member: member.name)
    licenses = dist_licenses or package_licenses
    if not licenses:
        raise SubsetError("wheel central directory lists no distribution rights member")
    selected = tuple(sorted((metadata, *licenses), key=lambda member: member.name))
    spans = _member_ranges(
        members=member_table,
        selected_names={member.name for member in selected},
        central_offset=central_offset,
    )
    rights_range = ByteRange(
        min(byte_range.start for byte_range in spans),
        max(byte_range.end for byte_range in spans),
    )
    return selected, rights_range


def _member_ranges(
    *, members: Iterable[ZipMember], selected_names: set[str], central_offset: int
) -> list[ByteRange]:
    ordered = sorted(members, key=lambda member: member.local_offset)
    ranges = []
    for index, member in enumerate(ordered):
        next_offset = (
            ordered[index + 1].local_offset if index + 1 < len(ordered) else central_offset
        )
        minimum_end = member.local_offset + LOCAL.size + member.compressed_bytes - 1
        if next_offset <= member.local_offset or next_offset - 1 < minimum_end:
            raise SubsetError(f"overlapping or truncated local member span: {member.name}")
        if member.name in selected_names:
            ranges.append(ByteRange(member.local_offset, next_offset - 1))
    return ranges


def subtract_ranges(
    ranges: Iterable[ByteRange], *, retained: Iterable[ByteRange]
) -> tuple[ByteRange, ...]:
    """Return exact portions of non-overlapping ranges not covered by retained bytes."""

    sources = sorted(ranges)
    for previous, current in zip(sources, sources[1:], strict=False):
        if current.start <= previous.end:
            raise SubsetError("source byte ranges overlap")
    coverage: list[ByteRange] = []
    for item in sorted(retained):
        if coverage and item.start <= coverage[-1].end + 1:
            coverage[-1] = ByteRange(coverage[-1].start, max(coverage[-1].end, item.end))
        else:
            coverage.append(item)

    remaining: list[ByteRange] = []
    for source in sources:
        cursor = source.start
        for held in coverage:
            if held.end < cursor:
                continue
            if held.start > source.end:
                break
            if held.start > cursor:
                remaining.append(ByteRange(cursor, min(source.end, held.start - 1)))
            cursor = max(cursor, held.end + 1)
            if cursor > source.end:
                break
        if cursor <= source.end:
            remaining.append(ByteRange(cursor, source.end))
    return tuple(remaining)


def coalesce_ranges(ranges: Iterable[ByteRange], *, maximum_ranges: int) -> tuple[ByteRange, ...]:
    """Merge overlaps, then smallest gaps deterministically until the request cap fits."""

    if maximum_ranges < 1:
        raise SubsetError("maximum_ranges must be positive")
    merged: list[ByteRange] = []
    for item in sorted(ranges):
        if merged and item.start <= merged[-1].end + 1:
            merged[-1] = ByteRange(merged[-1].start, max(merged[-1].end, item.end))
        else:
            merged.append(item)
    while len(merged) > maximum_ranges:
        gaps = [merged[index + 1].start - merged[index].end - 1 for index in range(len(merged) - 1)]
        join_at = min(range(len(gaps)), key=lambda index: (gaps[index], index))
        combined = ByteRange(merged[join_at].start, merged[join_at + 1].end)
        merged[join_at : join_at + 2] = [combined]
    return tuple(merged)


def plan_subset(
    *,
    layout: ZipLayout,
    central_directory: bytes,
    members: Iterable[ZipMember],
    referenced_asset_members: Iterable[str],
    required_member_names: Iterable[str],
    maximum_member_ranges: int,
    prior_response_body_bytes: int,
    response_body_ceiling_bytes: int,
    declared_whole_sha256: str,
    retained_member_ranges: Iterable[ByteRange] = (),
) -> dict:
    """Return a deterministic plan or refuse before any member response is requested."""

    if prior_response_body_bytes < 0 or response_body_ceiling_bytes < 0:
        raise SubsetError("byte counters cannot be negative")
    if len(declared_whole_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in declared_whole_sha256
    ):
        raise SubsetError("declared_whole_sha256 must be 64 lowercase hexadecimal characters")
    member_table = tuple(members)
    parsed_table = parse_central_directory(central_directory, layout)
    if parsed_table != member_table:
        raise SubsetError("member table does not match the supplied central-directory bytes")
    required = set(required_member_names)
    for name in required:
        _safe_member_name(name)
    missing_required = sorted(required - {member.name for member in member_table})
    if missing_required:
        raise SubsetError(f"required members are absent: {missing_required}")
    selected = select_members(member_table, referenced_asset_members=referenced_asset_members)
    selected_names = {member.name for member in selected}
    unselected_required = sorted(required - selected_names)
    if unselected_required:
        raise SubsetError(f"required members were not selected: {unselected_required}")
    retained_ranges = tuple(sorted(retained_member_ranges))
    if any(item.end >= layout.central_offset for item in retained_ranges):
        raise SubsetError("retained member range reaches the central directory")
    selected_spans = _member_ranges(
        members=member_table,
        selected_names=selected_names,
        central_offset=layout.central_offset,
    )
    incremental_spans = subtract_ranges(selected_spans, retained=retained_ranges)
    ranges = coalesce_ranges(
        incremental_spans,
        maximum_ranges=maximum_member_ranges,
    )
    member_response_bytes = sum(item.length for item in ranges)
    selected_span_bytes = sum(item.length for item in selected_spans)
    incremental_span_bytes = sum(item.length for item in incremental_spans)
    retained_refetched_bytes = member_response_bytes - sum(
        item.length for item in subtract_ranges(ranges, retained=retained_ranges)
    )
    selected_payload_bytes = sum(
        member.uncompressed_bytes for member in selected if not member.is_directory
    )
    required = prior_response_body_bytes + member_response_bytes
    if required > response_body_ceiling_bytes:
        raise BudgetExceeded(required=required, ceiling=response_body_ceiling_bytes)
    return {
        "schema": "nisayon.a1-wheel-subset-plan.v2",
        "archive": {
            "bytes": layout.archive_bytes,
            "declared_sha256": declared_whole_sha256,
            "sha256_verified": False,
            "identity_boundary": "the whole archive is not held; the publisher digest is declared, not locally verified",
        },
        "central_directory": {
            "offset": layout.central_offset,
            "bytes": layout.central_bytes,
            "entries": layout.entries,
            "sha256": hashlib.sha256(central_directory).hexdigest(),
        },
        "selection": {
            "members_total": len(member_table),
            "members_selected": len(selected),
            "selected": [member.as_dict() for member in selected],
        },
        "member_ranges": [item.as_dict() for item in ranges],
        "retained_member_ranges": [item.as_dict() for item in retained_ranges],
        "storage_projection": {
            "sparse_archive_logical_bytes": layout.archive_bytes,
            "selected_extracted_payload_logical_bytes": selected_payload_bytes,
            "coexisting_logical_file_lengths_bytes": layout.archive_bytes + selected_payload_bytes,
            "excluded": "filesystem metadata, block rounding, fetched-range files, dependencies, runtime-generated files, and any deleted or non-coexisting intermediate",
        },
        "budget": {
            "prior_response_body_bytes": prior_response_body_bytes,
            "selected_local_span_bytes": selected_span_bytes,
            "reused_selected_span_bytes": selected_span_bytes - incremental_span_bytes,
            "incremental_local_span_bytes_before_coalescing": incremental_span_bytes,
            "retained_bytes_refetched_by_coalescing": retained_refetched_bytes,
            "member_response_body_bytes": member_response_bytes,
            "required_response_body_bytes": required,
            "response_body_ceiling_bytes": response_body_ceiling_bytes,
            "remaining_after_plan_bytes": response_body_ceiling_bytes - required,
            "maximum_member_ranges": maximum_member_ranges,
            "planned_member_ranges": len(ranges),
        },
        "operations": {
            "network_requests": 0,
            "environment_constructions": 0,
            "physics_steps": 0,
            "policy_actions": 0,
        },
    }


def materialize_sparse_archive(
    *, destination: Path, archive_bytes: int, fragments: Iterable[tuple[ByteRange, bytes]]
) -> dict:
    """Create one sparse archive from non-overlapping, exact-position fragments."""

    if archive_bytes < 1:
        raise SubsetError("archive_bytes must be positive")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"refusing to overwrite sparse archive {destination}")
    ordered = sorted(fragments, key=lambda item: item[0])
    previous_end = -1
    for byte_range, body in ordered:
        if byte_range.end >= archive_bytes:
            raise SubsetError("fragment extends beyond the declared archive")
        if byte_range.start <= previous_end:
            raise SubsetError("sparse archive fragments overlap")
        if len(body) != byte_range.length:
            raise SubsetError("fragment body length differs from its declared range")
        previous_end = byte_range.end

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.truncate(archive_bytes)
        for byte_range, body in ordered:
            stream.seek(byte_range.start)
            stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    metadata = destination.stat()
    return {
        "path": str(destination),
        "logical_bytes": metadata.st_size,
        "allocated_bytes": getattr(metadata, "st_blocks", 0) * 512,
        "fragments": [byte_range.as_dict() for byte_range, _body in ordered],
    }


def extract_subset_create_only(
    *, archive: Path, destination: Path, selected: Iterable[ZipMember]
) -> list[dict]:
    """Extract and hash selected members, retaining a partial destination on failure."""

    if archive.is_symlink() or not archive.is_file():
        raise SubsetError("sparse archive is absent, non-regular, or a symlink")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"refusing to overwrite extraction destination {destination}")
    destination.mkdir(parents=True)
    records = []
    try:
        with zipfile.ZipFile(archive) as wheel:
            info_by_name = {item.filename: item for item in wheel.infolist()}
            for member in sorted(selected, key=lambda item: item.name):
                info = info_by_name.get(member.name)
                if info is None:
                    raise SubsetError(
                        f"selected member is absent from sparse archive: {member.name}"
                    )
                if (
                    info.CRC != member.crc32
                    or info.compress_size != member.compressed_bytes
                    or info.file_size != member.uncompressed_bytes
                    or info.compress_type != member.compression
                    or info.header_offset != member.local_offset
                ):
                    raise SubsetError(f"selected member metadata changed: {member.name}")
                _safe_member_name(member.name)
                target = destination.joinpath(*member.name.rstrip("/").split("/"))
                if member.is_directory:
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                body_bytes = 0
                with wheel.open(info) as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        body_bytes += len(chunk)
                        digest.update(chunk)
                        output.write(chunk)
                if body_bytes != member.uncompressed_bytes:
                    raise SubsetError(f"extracted length differs: {member.name}")
                records.append(
                    {
                        "name": member.name,
                        "bytes": body_bytes,
                        "crc32": f"{member.crc32:08x}",
                        "sha256": digest.hexdigest(),
                    }
                )
    except (OSError, RuntimeError, zipfile.BadZipFile, zlib.error) as error:
        if isinstance(error, SubsetError):
            raise
        raise SubsetError(f"subset extraction failed: {type(error).__name__}: {error}") from error
    return records
