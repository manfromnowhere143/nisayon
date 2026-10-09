import hashlib
import importlib.util
import random
import sys
import warnings
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path("scripts/experiments/a1_wheel_subset.py")
SPEC = importlib.util.spec_from_file_location("a1_wheel_subset", SCRIPT)
subset = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = subset
SPEC.loader.exec_module(subset)


def _wheel_bytes(
    tmp_path: Path, *, unsafe_name: str | None = None, duplicate: bool = False
) -> bytes:
    path = tmp_path / "synthetic.whl"
    random_body = random.Random(7).randbytes(64 * 1024)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
        wheel.writestr("robosuite/__init__.py", b'__version__ = "1.5.1"\n')
        wheel.writestr("robosuite/models/assets/arenas/lift.xml", b"<mujoco />")
        wheel.writestr("robosuite/models/assets/textures/needed.png", b"needed")
        wheel.writestr("robosuite/models/assets/textures/unused.png", random_body)
        wheel.writestr("robosuite-1.5.1.dist-info/METADATA", b"Name: robosuite\n")
        wheel.writestr("robosuite-1.5.1.dist-info/LICENSE", b"synthetic terms")
        if unsafe_name is not None:
            wheel.writestr(unsafe_name, b"unsafe")
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                wheel.writestr("robosuite/__init__.py", b"duplicate")
    return path.read_bytes()


def _directory(blob: bytes):
    tail_bytes = min(len(blob), subset.MAX_EOCD_BYTES)
    tail_start = len(blob) - tail_bytes
    layout = subset.parse_eocd(
        tail=blob[tail_start:], tail_start=tail_start, archive_bytes=len(blob)
    )
    central = blob[layout.central_offset : layout.central_offset + layout.central_bytes]
    members = subset.parse_central_directory(central, layout)
    return layout, central, members


def _plan(blob: bytes, *, maximum_ranges: int = 64, ceiling: int = 10**9):
    layout, central, members = _directory(blob)
    plan = subset.plan_subset(
        layout=layout,
        central_directory=central,
        members=members,
        referenced_asset_members=["robosuite/models/assets/textures/needed.png"],
        required_member_names=[
            "robosuite-1.5.1.dist-info/METADATA",
            "robosuite-1.5.1.dist-info/LICENSE",
        ],
        maximum_member_ranges=maximum_ranges,
        prior_response_body_bytes=123,
        response_body_ceiling_bytes=ceiling,
        declared_whole_sha256="a" * 64,
    )
    selected_names = {item["name"] for item in plan["selection"]["selected"]}
    selected = tuple(member for member in members if member.name in selected_names)
    return layout, members, selected, plan


def test_plans_materializes_and_extracts_only_the_scoped_members(tmp_path):
    blob = _wheel_bytes(tmp_path)
    layout, _members, selected, plan = _plan(blob)
    member_ranges = [subset.ByteRange(item["start"], item["end"]) for item in plan["member_ranges"]]
    directory_range = subset.ByteRange(layout.central_offset, len(blob) - 1)
    fragments = [(item, blob[item.start : item.end + 1]) for item in member_ranges]
    fragments.append((directory_range, blob[directory_range.start :]))
    sparse = tmp_path / "partial.whl"

    sparse_record = subset.materialize_sparse_archive(
        destination=sparse, archive_bytes=len(blob), fragments=fragments
    )
    extracted = subset.extract_subset_create_only(
        archive=sparse, destination=tmp_path / "runtime", selected=selected
    )

    extracted_names = {item["name"] for item in extracted}
    assert "robosuite/__init__.py" in extracted_names
    assert "robosuite/models/assets/arenas/lift.xml" in extracted_names
    assert "robosuite/models/assets/textures/needed.png" in extracted_names
    assert "robosuite/models/assets/textures/unused.png" not in extracted_names
    assert sparse_record["logical_bytes"] == len(blob)
    assert plan["archive"]["declared_sha256"] == "a" * 64
    assert plan["archive"]["sha256_verified"] is False
    assert plan["operations"]["network_requests"] == 0


def test_plan_refuses_before_member_fetch_when_body_cap_is_too_small(tmp_path):
    blob = _wheel_bytes(tmp_path)
    with pytest.raises(subset.BudgetExceeded) as caught:
        _plan(blob, ceiling=124)

    assert caught.value.required > caught.value.ceiling


def test_plan_rejects_a_member_table_not_bound_to_the_directory(tmp_path):
    blob = _wheel_bytes(tmp_path)
    layout, central, members = _directory(blob)

    with pytest.raises(subset.SubsetError, match="member table does not match"):
        subset.plan_subset(
            layout=layout,
            central_directory=central,
            members=members[:-1],
            referenced_asset_members=["robosuite/models/assets/textures/needed.png"],
            required_member_names=["robosuite-1.5.1.dist-info/METADATA"],
            maximum_member_ranges=64,
            prior_response_body_bytes=0,
            response_body_ceiling_bytes=10**9,
            declared_whole_sha256="a" * 64,
        )


def test_plan_rejects_a_missing_rights_member_before_member_fetch(tmp_path):
    blob = _wheel_bytes(tmp_path)
    layout, central, members = _directory(blob)

    with pytest.raises(subset.SubsetError, match="required members are absent"):
        subset.plan_subset(
            layout=layout,
            central_directory=central,
            members=members,
            referenced_asset_members=["robosuite/models/assets/textures/needed.png"],
            required_member_names=["robosuite-1.5.1.dist-info/COPYING"],
            maximum_member_ranges=64,
            prior_response_body_bytes=0,
            response_body_ceiling_bytes=10**9,
            declared_whole_sha256="a" * 64,
        )


def test_rights_range_prefers_dist_info_and_covers_metadata_and_all_licenses(tmp_path):
    path = tmp_path / "rights.whl"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as wheel:
        wheel.writestr("robosuite/LICENSE", b"fallback")
        wheel.writestr("robosuite-1.5.1.dist-info/LICENSE", b"primary")
        wheel.writestr("robosuite-1.5.1.dist-info/LICENSE.third-party", b"third party")
        wheel.writestr("robosuite-1.5.1.dist-info/licenses/NOTICE", b"notice")
        wheel.writestr("robosuite-1.5.1.dist-info/METADATA", b"Name: robosuite\n")
    blob = path.read_bytes()
    layout, _central, members = _directory(blob)

    selected, byte_range = subset.plan_rights_range(
        members=members,
        central_offset=layout.central_offset,
    )

    assert [member.name for member in selected] == [
        "robosuite-1.5.1.dist-info/LICENSE",
        "robosuite-1.5.1.dist-info/LICENSE.third-party",
        "robosuite-1.5.1.dist-info/METADATA",
        "robosuite-1.5.1.dist-info/licenses/NOTICE",
    ]
    assert byte_range.start == min(member.local_offset for member in selected)
    assert byte_range.end < layout.central_offset


def test_rights_range_uses_package_license_only_as_fallback(tmp_path):
    path = tmp_path / "fallback-rights.whl"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as wheel:
        wheel.writestr("robosuite/LICENSE.txt", b"fallback")
        wheel.writestr("robosuite-1.5.1.dist-info/METADATA", b"Name: robosuite\n")
    blob = path.read_bytes()
    layout, _central, members = _directory(blob)

    selected, _byte_range = subset.plan_rights_range(
        members=members,
        central_offset=layout.central_offset,
    )

    assert [member.name for member in selected] == [
        "robosuite-1.5.1.dist-info/METADATA",
        "robosuite/LICENSE.txt",
    ]


def test_rights_range_rejects_missing_metadata_or_license(tmp_path):
    missing_metadata = tmp_path / "missing-metadata.whl"
    with zipfile.ZipFile(missing_metadata, "w") as wheel:
        wheel.writestr("robosuite-1.5.1.dist-info/LICENSE", b"terms")
    blob = missing_metadata.read_bytes()
    layout, _central, members = _directory(blob)
    with pytest.raises(subset.SubsetError, match="metadata member is absent"):
        subset.plan_rights_range(members=members, central_offset=layout.central_offset)

    missing_license = tmp_path / "missing-license.whl"
    with zipfile.ZipFile(missing_license, "w") as wheel:
        wheel.writestr("robosuite-1.5.1.dist-info/METADATA", b"Name: robosuite\n")
    blob = missing_license.read_bytes()
    layout, _central, members = _directory(blob)
    with pytest.raises(subset.SubsetError, match="no distribution rights member"):
        subset.plan_rights_range(members=members, central_offset=layout.central_offset)


def test_rights_range_does_not_promote_a_nested_asset_license(tmp_path):
    path = tmp_path / "asset-license-only.whl"
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr("robosuite/models/assets/LICENSE", b"asset-only terms")
        wheel.writestr("robosuite-1.5.1.dist-info/METADATA", b"Name: robosuite\n")
    blob = path.read_bytes()
    layout, _central, members = _directory(blob)

    with pytest.raises(subset.SubsetError, match="no distribution rights member"):
        subset.plan_rights_range(members=members, central_offset=layout.central_offset)


def test_rights_range_extracts_only_rights_members_despite_incidental_bytes(tmp_path):
    path = tmp_path / "rights-with-incidental.whl"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as wheel:
        wheel.writestr("robosuite-1.5.1.dist-info/LICENSE", b"terms")
        wheel.writestr("robosuite/incidental.py", b"raise RuntimeError('do not execute')\n")
        wheel.writestr("robosuite-1.5.1.dist-info/METADATA", b"Name: robosuite\n")
    blob = path.read_bytes()
    layout, _central, members = _directory(blob)
    selected, rights_range = subset.plan_rights_range(
        members=members,
        central_offset=layout.central_offset,
    )
    incidental = next(member for member in members if member.name == "robosuite/incidental.py")
    assert rights_range.start < incidental.local_offset < rights_range.end

    terminal_range = subset.ByteRange(layout.central_offset, len(blob) - 1)
    sparse = tmp_path / "rights-partial.whl"
    subset.materialize_sparse_archive(
        destination=sparse,
        archive_bytes=len(blob),
        fragments=[
            (rights_range, blob[rights_range.start : rights_range.end + 1]),
            (terminal_range, blob[terminal_range.start :]),
        ],
    )
    destination = tmp_path / "rights-only"
    records = subset.extract_subset_create_only(
        archive=sparse,
        destination=destination,
        selected=selected,
    )

    assert {record["name"] for record in records} == {
        "robosuite-1.5.1.dist-info/LICENSE",
        "robosuite-1.5.1.dist-info/METADATA",
    }
    assert not (destination / "robosuite/incidental.py").exists()


def test_coalescing_uses_smallest_gap_and_accounts_for_it():
    planned = subset.coalesce_ranges(
        [subset.ByteRange(0, 9), subset.ByteRange(20, 29), subset.ByteRange(100, 109)],
        maximum_ranges=2,
    )

    assert planned == (subset.ByteRange(0, 29), subset.ByteRange(100, 109))
    assert sum(item.length for item in planned) == 40


def test_subtract_ranges_reuses_retained_prefix_middle_and_suffix():
    remaining = subset.subtract_ranges(
        [subset.ByteRange(0, 99), subset.ByteRange(200, 299)],
        retained=[
            subset.ByteRange(0, 9),
            subset.ByteRange(40, 59),
            subset.ByteRange(90, 209),
            subset.ByteRange(290, 299),
        ],
    )

    assert remaining == (
        subset.ByteRange(10, 39),
        subset.ByteRange(60, 89),
        subset.ByteRange(210, 289),
    )


def test_subset_plan_counts_only_incremental_bytes_after_rights_range(tmp_path):
    blob = _wheel_bytes(tmp_path)
    layout, central, members = _directory(blob)
    _rights_members, rights_range = subset.plan_rights_range(
        members=members,
        central_offset=layout.central_offset,
    )
    common = {
        "layout": layout,
        "central_directory": central,
        "members": members,
        "referenced_asset_members": ["robosuite/models/assets/textures/needed.png"],
        "required_member_names": [
            "robosuite-1.5.1.dist-info/METADATA",
            "robosuite-1.5.1.dist-info/LICENSE",
        ],
        "maximum_member_ranges": 64,
        "prior_response_body_bytes": rights_range.length,
        "response_body_ceiling_bytes": 10**9,
        "declared_whole_sha256": "a" * 64,
    }

    repeated = subset.plan_subset(**common)
    reused = subset.plan_subset(**common, retained_member_ranges=[rights_range])

    assert reused["schema"] == "nisayon.a1-wheel-subset-plan.v2"
    assert reused["budget"]["reused_selected_span_bytes"] == rights_range.length
    assert reused["budget"]["retained_bytes_refetched_by_coalescing"] == 0
    assert (
        repeated["budget"]["member_response_body_bytes"]
        - reused["budget"]["member_response_body_bytes"]
        == rights_range.length
    )
    assert all(
        item["end"] < rights_range.start or item["start"] > rights_range.end
        for item in reused["member_ranges"]
    )
    selected_payload_bytes = sum(
        member.uncompressed_bytes
        for member in members
        if member.name in {item["name"] for item in reused["selection"]["selected"]}
        and not member.is_directory
    )
    assert reused["storage_projection"] == {
        "sparse_archive_logical_bytes": len(blob),
        "selected_extracted_payload_logical_bytes": selected_payload_bytes,
        "coexisting_logical_file_lengths_bytes": len(blob) + selected_payload_bytes,
        "excluded": "filesystem metadata, block rounding, fetched-range files, dependencies, runtime-generated files, and any deleted or non-coexisting intermediate",
    }

    selected_names = {item["name"] for item in reused["selection"]["selected"]}
    middle_range = next(
        byte_range
        for member, byte_range in zip(
            sorted(members, key=lambda item: item.local_offset),
            subset._member_ranges(
                members=members,
                selected_names={member.name for member in members},
                central_offset=layout.central_offset,
            ),
            strict=True,
        )
        if member.name == "robosuite/models/assets/textures/needed.png"
        and member.name in selected_names
    )
    one_request = subset.plan_subset(
        **{
            **common,
            "maximum_member_ranges": 1,
            "prior_response_body_bytes": middle_range.length,
        },
        retained_member_ranges=[middle_range],
    )
    assert one_request["budget"]["retained_bytes_refetched_by_coalescing"] > 0
    assert one_request["budget"]["member_response_body_bytes"] == sum(
        item["bytes"] for item in one_request["member_ranges"]
    )


def test_subset_plan_rejects_a_retained_range_in_the_directory(tmp_path):
    blob = _wheel_bytes(tmp_path)
    layout, central, members = _directory(blob)

    with pytest.raises(subset.SubsetError, match="reaches the central directory"):
        subset.plan_subset(
            layout=layout,
            central_directory=central,
            members=members,
            referenced_asset_members=["robosuite/models/assets/textures/needed.png"],
            required_member_names=["robosuite-1.5.1.dist-info/METADATA"],
            maximum_member_ranges=64,
            prior_response_body_bytes=0,
            response_body_ceiling_bytes=10**9,
            declared_whole_sha256="a" * 64,
            retained_member_ranges=[subset.ByteRange(layout.central_offset, layout.central_offset)],
        )


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a\\b"])
def test_central_directory_rejects_unsafe_member_names(tmp_path, name):
    blob = _wheel_bytes(tmp_path, unsafe_name=name)
    tail_bytes = min(len(blob), subset.MAX_EOCD_BYTES)
    layout = subset.parse_eocd(
        tail=blob[-tail_bytes:], tail_start=len(blob) - tail_bytes, archive_bytes=len(blob)
    )
    central = blob[layout.central_offset : layout.central_offset + layout.central_bytes]

    with pytest.raises(subset.SubsetError, match="unsafe ZIP member name"):
        subset.parse_central_directory(central, layout)


def test_central_directory_rejects_duplicate_member_names(tmp_path):
    blob = _wheel_bytes(tmp_path, duplicate=True)
    tail_bytes = min(len(blob), subset.MAX_EOCD_BYTES)
    layout = subset.parse_eocd(
        tail=blob[-tail_bytes:], tail_start=len(blob) - tail_bytes, archive_bytes=len(blob)
    )
    central = blob[layout.central_offset : layout.central_offset + layout.central_bytes]

    with pytest.raises(subset.SubsetError, match="duplicate ZIP member name"):
        subset.parse_central_directory(central, layout)


def test_extraction_rejects_corrupted_selected_member_and_retains_failure(tmp_path):
    blob = bytearray(_wheel_bytes(tmp_path))
    layout, _members, selected, plan = _plan(bytes(blob))
    target = next(member for member in selected if member.name == "robosuite/__init__.py")
    local = subset.LOCAL.unpack_from(blob, target.local_offset)
    assert local[0] == subset.LOCAL_SIGNATURE
    data_offset = target.local_offset + subset.LOCAL.size + local[-2] + local[-1]
    blob[data_offset] ^= 0xFF
    member_ranges = [subset.ByteRange(item["start"], item["end"]) for item in plan["member_ranges"]]
    directory_range = subset.ByteRange(layout.central_offset, len(blob) - 1)
    fragments = [(item, bytes(blob[item.start : item.end + 1])) for item in member_ranges]
    fragments.append((directory_range, bytes(blob[directory_range.start :])))
    sparse = tmp_path / "corrupted.whl"
    subset.materialize_sparse_archive(
        destination=sparse, archive_bytes=len(blob), fragments=fragments
    )
    destination = tmp_path / "failed-runtime"

    with pytest.raises(subset.SubsetError, match="subset extraction failed"):
        subset.extract_subset_create_only(
            archive=sparse, destination=destination, selected=selected
        )

    assert destination.is_dir()
    assert sparse.is_file()


def test_eocd_rejects_zip64_sentinel():
    tail = subset.EOCD.pack(subset.EOCD_SIGNATURE, 0, 0, 0xFFFF, 0xFFFF, 0, 0, 0)

    with pytest.raises(subset.SubsetError, match="ZIP64"):
        subset.parse_eocd(tail=tail, tail_start=0, archive_bytes=len(tail))


def test_large_suffix_searches_only_the_terminal_eocd_window(tmp_path):
    blob = _wheel_bytes(tmp_path)
    assert len(blob) > subset.MAX_EOCD_BYTES

    layout = subset.parse_eocd(tail=blob, tail_start=0, archive_bytes=len(blob))
    central = subset.central_directory_from_suffix(suffix=blob, suffix_start=0, layout=layout)

    assert len(subset.parse_central_directory(central, layout)) == layout.entries


def test_central_directory_requires_a_suffix_that_actually_contains_it(tmp_path):
    path = tmp_path / "many-members.whl"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as wheel:
        for index in range(1_500):
            wheel.writestr(f"robosuite/member-{index:04d}.py", b"pass\n")
    blob = path.read_bytes()
    tail = blob[-subset.MAX_EOCD_BYTES :]
    tail_start = len(blob) - len(tail)
    layout = subset.parse_eocd(
        tail=tail,
        tail_start=tail_start,
        archive_bytes=len(blob),
    )

    with pytest.raises(subset.SubsetError, match="begins before supplied suffix"):
        subset.central_directory_from_suffix(
            suffix=tail,
            suffix_start=tail_start,
            layout=layout,
        )

    complete_suffix = blob[layout.central_offset :]
    central = subset.central_directory_from_suffix(
        suffix=complete_suffix,
        suffix_start=layout.central_offset,
        layout=layout,
    )
    members = subset.parse_central_directory(central, layout)
    assert len(members) == 1_500


def test_central_directory_assembles_from_suffix_and_exact_missing_prefix(tmp_path):
    path = tmp_path / "fragmented-directory.whl"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as wheel:
        for index in range(1_500):
            wheel.writestr(f"robosuite/member-{index:04d}.py", b"pass\n")
    blob = path.read_bytes()
    suffix = blob[-subset.MAX_EOCD_BYTES :]
    suffix_start = len(blob) - len(suffix)
    layout = subset.parse_eocd(
        tail=suffix,
        tail_start=suffix_start,
        archive_bytes=len(blob),
    )
    prefix_range = subset.ByteRange(layout.central_offset, suffix_start - 1)
    suffix_range = subset.ByteRange(suffix_start, len(blob) - 1)

    central = subset.central_directory_from_fragments(
        layout=layout,
        fragments=[
            (suffix_range, suffix),
            (prefix_range, blob[prefix_range.start : prefix_range.end + 1]),
        ],
    )

    assert central == blob[layout.central_offset : layout.eocd_offset]
    assert len(subset.parse_central_directory(central, layout)) == 1_500


def test_central_directory_fragment_assembly_rejects_gap_and_overlap(tmp_path):
    blob = _wheel_bytes(tmp_path)
    layout, central, _members = _directory(blob)
    midpoint = layout.central_offset + layout.central_bytes // 2
    first = subset.ByteRange(layout.central_offset, midpoint - 1)
    second_with_gap = subset.ByteRange(midpoint + 1, layout.eocd_offset - 1)
    second_with_overlap = subset.ByteRange(midpoint - 1, layout.eocd_offset - 1)

    with pytest.raises(subset.SubsetError, match="have a gap"):
        subset.central_directory_from_fragments(
            layout=layout,
            fragments=[
                (first, central[: first.length]),
                (second_with_gap, central[first.length + 1 :]),
            ],
        )
    with pytest.raises(subset.SubsetError, match="overlap"):
        subset.central_directory_from_fragments(
            layout=layout,
            fragments=[
                (first, central[: first.length]),
                (second_with_overlap, central[first.length - 1 :]),
            ],
        )


def test_selected_member_hash_is_of_extracted_bytes(tmp_path):
    blob = _wheel_bytes(tmp_path)
    layout, _members, selected, plan = _plan(blob)
    ranges = [subset.ByteRange(item["start"], item["end"]) for item in plan["member_ranges"]]
    directory_range = subset.ByteRange(layout.central_offset, len(blob) - 1)
    fragments = [(item, blob[item.start : item.end + 1]) for item in ranges]
    fragments.append((directory_range, blob[directory_range.start :]))
    sparse = tmp_path / "hash.whl"
    subset.materialize_sparse_archive(
        destination=sparse, archive_bytes=len(blob), fragments=fragments
    )
    destination = tmp_path / "hash-runtime"

    records = subset.extract_subset_create_only(
        archive=sparse, destination=destination, selected=selected
    )
    init = next(item for item in records if item["name"] == "robosuite/__init__.py")

    assert (
        init["sha256"]
        == hashlib.sha256((destination / "robosuite/__init__.py").read_bytes()).hexdigest()
    )
