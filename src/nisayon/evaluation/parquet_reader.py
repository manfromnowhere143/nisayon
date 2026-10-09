"""A small pure-Python Parquet reader for low-dimensional LeRobot episode files.

The evaluation lane needs to read the retained numeric demonstration files without
adding a dependency, and with a parse whose identity is recorded. This module reads the
subset of the Parquet format those files use: Thrift compact footer metadata, Snappy or
uncompressed pages, data pages v1 and v2, dictionary pages, PLAIN values for FLOAT,
DOUBLE, INT32, INT64 and BOOLEAN, RLE/bit-packed hybrid levels and dictionary indices,
and one level of LIST nesting. Anything else is refused with a stable reason rather than
guessed. Floats are returned as Python floats holding the exact float32 value read from
the file; no arithmetic is performed here.

Parse identity: ``parse_identity()`` returns the sha256 of this module's source so a
record can say exactly which reader produced its values. The Parquet and Thrift formats
are the Apache Parquet project's; this file implements only what is needed to read them.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from pathlib import Path

from .schema import Malformed

# Thrift compact protocol type codes.
_T_BOOL_TRUE, _T_BOOL_FALSE, _T_BYTE, _T_I16, _T_I32, _T_I64 = 1, 2, 3, 4, 5, 6
_T_DOUBLE, _T_BINARY, _T_LIST, _T_SET, _T_MAP, _T_STRUCT = 7, 8, 9, 10, 11, 12

PHYSICAL = {
    0: "BOOLEAN",
    1: "INT32",
    2: "INT64",
    3: "INT96",
    4: "FLOAT",
    5: "DOUBLE",
    6: "BYTE_ARRAY",
    7: "FIXED_LEN_BYTE_ARRAY",
}
REPETITION = {0: "REQUIRED", 1: "OPTIONAL", 2: "REPEATED"}
CODEC = {
    0: "UNCOMPRESSED",
    1: "SNAPPY",
    2: "GZIP",
    3: "LZO",
    4: "BROTLI",
    5: "LZ4",
    6: "ZSTD",
    7: "LZ4_RAW",
}
ENCODING = {
    0: "PLAIN",
    2: "PLAIN_DICTIONARY",
    3: "RLE",
    4: "BIT_PACKED",
    5: "DELTA_BINARY_PACKED",
    6: "DELTA_LENGTH_BYTE_ARRAY",
    7: "DELTA_BYTE_ARRAY",
    8: "RLE_DICTIONARY",
    9: "BYTE_STREAM_SPLIT",
}
PAGE = {0: "DATA_PAGE", 1: "INDEX_PAGE", 2: "DICTIONARY_PAGE", 3: "DATA_PAGE_V2"}


def parse_identity() -> dict:
    source = Path(__file__).read_bytes()
    return {
        "module": "nisayon.evaluation.parquet_reader",
        "sha256": hashlib.sha256(source).hexdigest(),
        "bytes": len(source),
    }


# --- Thrift compact protocol ---------------------------------------------------------------


class _Cursor:
    __slots__ = ("data", "pos")

    def __init__(self, data: bytes, pos: int = 0) -> None:
        self.data = data
        self.pos = pos

    def byte(self) -> int:
        if self.pos >= len(self.data):
            raise Malformed("thrift", "unexpected end of data")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def take(self, count: int) -> bytes:
        if self.pos + count > len(self.data):
            raise Malformed("thrift", f"unexpected end of data reading {count} bytes")
        chunk = self.data[self.pos : self.pos + count]
        self.pos += count
        return chunk

    def varint(self) -> int:
        result = 0
        shift = 0
        while True:
            value = self.byte()
            result |= (value & 0x7F) << shift
            if not value & 0x80:
                return result
            shift += 7
            if shift > 70:
                raise Malformed("thrift", "varint too long")

    def zigzag(self) -> int:
        raw = self.varint()
        return (raw >> 1) ^ -(raw & 1)


def _read_value(cursor: _Cursor, kind: int) -> object:
    if kind == _T_BOOL_TRUE:
        return True
    if kind == _T_BOOL_FALSE:
        return False
    if kind == _T_BYTE:
        return struct.unpack("<b", cursor.take(1))[0]
    if kind in (_T_I16, _T_I32, _T_I64):
        return cursor.zigzag()
    if kind == _T_DOUBLE:
        return struct.unpack("<d", cursor.take(8))[0]
    if kind == _T_BINARY:
        return cursor.take(cursor.varint())
    if kind in (_T_LIST, _T_SET):
        header = cursor.byte()
        size = header >> 4
        element = header & 0x0F
        if size == 15:
            size = cursor.varint()
        return [_read_value(cursor, element) for _ in range(size)]
    if kind == _T_MAP:
        size = cursor.varint()
        if size == 0:
            return {}
        types = cursor.byte()
        key_type, value_type = types >> 4, types & 0x0F
        return {_read_value(cursor, key_type): _read_value(cursor, value_type) for _ in range(size)}
    if kind == _T_STRUCT:
        return _read_struct(cursor)
    raise Malformed("thrift", f"unsupported field type {kind}")


def _read_struct(cursor: _Cursor) -> dict[int, object]:
    fields: dict[int, object] = {}
    last_id = 0
    while True:
        header = cursor.byte()
        if header == 0:
            return fields
        delta = header >> 4
        kind = header & 0x0F
        if delta:
            field_id = last_id + delta
        else:
            field_id = cursor.zigzag()
        fields[field_id] = _read_value(cursor, kind)
        last_id = field_id


# --- Snappy ---------------------------------------------------------------------------------


def snappy_decompress(data: bytes) -> bytes:
    cursor = _Cursor(data)
    expected = cursor.varint()
    out = bytearray()
    while cursor.pos < len(data):
        tag = cursor.byte()
        kind = tag & 3
        if kind == 0:
            length = (tag >> 2) + 1
            if length > 60:
                extra = length - 60
                length = int.from_bytes(cursor.take(extra), "little") + 1
            out += cursor.take(length)
            continue
        if kind == 1:
            length = ((tag >> 2) & 7) + 4
            offset = ((tag >> 5) << 8) | cursor.byte()
        elif kind == 2:
            length = (tag >> 2) + 1
            offset = int.from_bytes(cursor.take(2), "little")
        else:
            length = (tag >> 2) + 1
            offset = int.from_bytes(cursor.take(4), "little")
        if offset == 0 or offset > len(out):
            raise Malformed("snappy", f"invalid copy offset {offset} at output {len(out)}")
        start = len(out) - offset
        for i in range(length):
            out.append(out[start + i])
    if len(out) != expected:
        raise Malformed("snappy", f"decompressed {len(out)} bytes, header declared {expected}")
    return bytes(out)


# --- RLE / bit-packed hybrid ------------------------------------------------------------------


def _bit_width(max_value: int) -> int:
    return max_value.bit_length()


def read_hybrid(cursor: _Cursor, bit_width: int, count: int) -> list[int]:
    """Read ``count`` values of the RLE/bit-packed hybrid encoding."""
    values: list[int] = []
    if bit_width == 0:
        return [0] * count
    byte_width = (bit_width + 7) // 8
    mask = (1 << bit_width) - 1
    while len(values) < count:
        header = cursor.varint()
        if header & 1 == 0:
            run = header >> 1
            value = int.from_bytes(cursor.take(byte_width), "little")
            values.extend([value] * run)
        else:
            groups = header >> 1
            raw = cursor.take(groups * bit_width)
            bits = int.from_bytes(raw, "little")
            for index in range(groups * 8):
                values.append((bits >> (index * bit_width)) & mask)
                if len(values) >= count and index == groups * 8 - 1:
                    break
    return values[:count]


# --- Schema ---------------------------------------------------------------------------------


@dataclass
class Column:
    name: str
    path: tuple[str, ...]
    physical: str
    max_definition: int
    max_repetition: int
    nested_list: bool
    repetition_path: tuple[str, ...] = field(default_factory=tuple)


def _schema_columns(elements: list[dict]) -> list[Column]:
    """Flatten the schema tree into leaf columns with their level bounds."""
    columns: list[Column] = []
    index = 1  # skip the root

    def walk(
        prefix: tuple[str, ...], definition: int, repetition: int, reps: tuple[str, ...]
    ) -> None:
        nonlocal index
        element = elements[index]
        index += 1
        name = (
            element[4].decode("utf-8") if isinstance(element.get(4), bytes) else str(element.get(4))
        )
        rep_kind = REPETITION.get(element.get(3, 0), "REQUIRED")
        if rep_kind == "OPTIONAL":
            definition += 1
        elif rep_kind == "REPEATED":
            definition += 1
            repetition += 1
            reps = reps + (name,)
        children = element.get(5, 0) or 0
        path = prefix + (name,)
        if children:
            for _ in range(children):
                walk(path, definition, repetition, reps)
        else:
            columns.append(
                Column(
                    name=path[0],
                    path=path,
                    physical=PHYSICAL.get(element.get(1), f"type{element.get(1)}"),
                    max_definition=definition,
                    max_repetition=repetition,
                    nested_list=repetition > 0,
                    repetition_path=reps,
                )
            )

    root = elements[0]
    for _ in range(root.get(5, 0) or 0):
        walk((), 0, 0, ())
    return columns


# --- Pages ----------------------------------------------------------------------------------


def _decode_plain(data: bytes, physical: str, count: int) -> list:
    if physical == "FLOAT":
        return list(struct.unpack(f"<{count}f", data[: 4 * count]))
    if physical == "DOUBLE":
        return list(struct.unpack(f"<{count}d", data[: 8 * count]))
    if physical == "INT32":
        return list(struct.unpack(f"<{count}i", data[: 4 * count]))
    if physical == "INT64":
        return list(struct.unpack(f"<{count}q", data[: 8 * count]))
    if physical == "BOOLEAN":
        bits = int.from_bytes(data[: (count + 7) // 8], "little")
        return [bool((bits >> i) & 1) for i in range(count)]
    raise Malformed("parquet", f"unsupported physical type {physical} for PLAIN decoding")


def _read_page_header(cursor: _Cursor) -> dict:
    raw = _read_struct(cursor)
    return {
        "type": PAGE.get(raw.get(1), f"page{raw.get(1)}"),
        "uncompressed": raw.get(2),
        "compressed": raw.get(3),
        "data_v1": raw.get(5),
        "dictionary": raw.get(7),
        "data_v2": raw.get(8),
    }


def _decompress(codec: str, data: bytes, uncompressed: int) -> bytes:
    if codec == "UNCOMPRESSED":
        return data
    if codec == "SNAPPY":
        out = snappy_decompress(data)
        if len(out) != uncompressed:
            raise Malformed(
                "parquet", f"snappy output {len(out)} bytes, page declared {uncompressed}"
            )
        return out
    raise Malformed("parquet", f"unsupported compression codec {codec}")


def _read_column_chunk(
    data: bytes, meta: dict, column: Column
) -> tuple[list, list[int], list[int], dict]:
    """Return values, definition levels and repetition levels for one column chunk."""
    codec = CODEC.get(meta.get(4), f"codec{meta.get(4)}")
    physical = PHYSICAL.get(meta.get(1), column.physical)
    num_values = meta.get(5)
    start = meta.get(11) if meta.get(11) is not None else meta.get(9)
    if meta.get(11) is not None and meta.get(9) is not None:
        start = min(meta[11], meta[9])
    cursor = _Cursor(data, start)
    dictionary: list | None = None
    values: list = []
    definitions: list[int] = []
    repetitions: list[int] = []
    encodings_seen: set[str] = set()
    pages = 0
    while len(values) < num_values:
        header = _read_page_header(cursor)
        payload = cursor.take(header["compressed"])
        pages += 1
        if header["type"] == "DICTIONARY_PAGE":
            page = _decompress(codec, payload, header["uncompressed"])
            count = header["dictionary"][1]
            dictionary = _decode_plain(page, physical, count)
            encodings_seen.add("dictionary_page")
            continue
        if header["type"] == "DATA_PAGE":
            info = header["data_v1"]
            count = info[1]
            encoding = ENCODING.get(info[2], f"encoding{info[2]}")
            page = _decompress(codec, payload, header["uncompressed"])
            body = _Cursor(page)
            if column.max_repetition > 0:
                length = struct.unpack("<I", body.take(4))[0]
                repetitions.extend(
                    read_hybrid(
                        _Cursor(body.take(length)), _bit_width(column.max_repetition), count
                    )
                )
            else:
                repetitions.extend([0] * count)
            if column.max_definition > 0:
                length = struct.unpack("<I", body.take(4))[0]
                definitions.extend(
                    read_hybrid(
                        _Cursor(body.take(length)), _bit_width(column.max_definition), count
                    )
                )
            else:
                definitions.extend([column.max_definition] * count)
            present = sum(1 for level in definitions[-count:] if level == column.max_definition)
            rest = page[body.pos :]
        elif header["type"] == "DATA_PAGE_V2":
            info = header["data_v2"]
            count = info[1]
            encoding = ENCODING.get(info[4], f"encoding{info[4]}")
            def_len = info.get(5, 0) or 0
            rep_len = info.get(6, 0) or 0
            compressed_flag = info.get(7, True)
            levels = payload[: rep_len + def_len]
            if column.max_repetition > 0:
                repetitions.extend(
                    read_hybrid(_Cursor(levels[:rep_len]), _bit_width(column.max_repetition), count)
                )
            else:
                repetitions.extend([0] * count)
            if column.max_definition > 0:
                definitions.extend(
                    read_hybrid(
                        _Cursor(levels[rep_len : rep_len + def_len]),
                        _bit_width(column.max_definition),
                        count,
                    )
                )
            else:
                definitions.extend([column.max_definition] * count)
            present = sum(1 for level in definitions[-count:] if level == column.max_definition)
            body_bytes = payload[rep_len + def_len :]
            rest = (
                _decompress(codec, body_bytes, header["uncompressed"] - rep_len - def_len)
                if compressed_flag
                else body_bytes
            )
        else:
            raise Malformed("parquet", f"unsupported page type {header['type']}")
        encodings_seen.add(encoding)
        if encoding == "PLAIN":
            values.extend(_decode_plain(rest, physical, present))
        elif encoding in ("PLAIN_DICTIONARY", "RLE_DICTIONARY"):
            if dictionary is None:
                raise Malformed("parquet", "dictionary-encoded page without a dictionary page")
            width = rest[0]
            indices = read_hybrid(_Cursor(rest, 1), width, present)
            values.extend(dictionary[i] for i in indices)
        else:
            raise Malformed("parquet", f"unsupported value encoding {encoding}")
    return (
        values,
        definitions,
        repetitions,
        {
            "codec": codec,
            "physical": physical,
            "encodings": sorted(encodings_seen),
            "pages": pages,
            "dictionary_size": None if dictionary is None else len(dictionary),
        },
    )


def _assemble(column: Column, values: list, definitions: list[int], repetitions: list[int]) -> list:
    """Rebuild rows from levels: flat columns give one value per row, LIST columns a list."""
    if not column.nested_list:
        rows: list = []
        cursor = 0
        for level in definitions:
            if level == column.max_definition:
                rows.append(values[cursor])
                cursor += 1
            else:
                rows.append(None)
        return rows
    rows = []
    current: list | None = None
    cursor = 0
    for level, rep in zip(definitions, repetitions, strict=True):
        if rep == 0:
            if current is not None:
                rows.append(current)
            current = [] if level >= column.max_definition - 1 else None
        if level == column.max_definition:
            if current is None:
                current = []
            current.append(values[cursor])
            cursor += 1
    if current is not None or definitions:
        rows.append(current)
    if cursor != len(values):
        raise Malformed(
            "parquet", f"{len(values) - cursor} values left unassigned in {column.name}"
        )
    return rows


# --- Public API -----------------------------------------------------------------------------


def read_metadata(data: bytes) -> dict:
    if len(data) < 12 or data[:4] != b"PAR1" or data[-4:] != b"PAR1":
        raise Malformed("parquet", "missing PAR1 magic")
    footer_length = struct.unpack("<I", data[-8:-4])[0]
    if footer_length + 12 > len(data):
        raise Malformed("parquet", f"footer length {footer_length} exceeds file")
    raw = _read_struct(_Cursor(data[-8 - footer_length : -8]))
    elements = raw.get(2)
    if not isinstance(elements, list) or not elements:
        raise Malformed("parquet", "schema missing")
    columns = _schema_columns(elements)
    key_values = {}
    for item in raw.get(5) or []:
        key = item.get(1)
        value = item.get(2)
        key_values[key.decode("utf-8") if isinstance(key, bytes) else key] = (
            value.decode("utf-8", "replace") if isinstance(value, bytes) else value
        )
    created_by = raw.get(6)
    return {
        "version": raw.get(1),
        "num_rows": raw.get(3),
        "created_by": created_by.decode("utf-8", "replace")
        if isinstance(created_by, bytes)
        else created_by,
        "row_groups": raw.get(4) or [],
        "columns": columns,
        "key_value_metadata": key_values,
    }


def read_parquet(path: Path) -> dict:
    """Read every column of a small Parquet file into Python lists.

    Returns ``{"columns": {name: rows}, "num_rows", "created_by", "column_info": {name: {...}},
    "sha256", "bytes"}``. Values are exact: float32 values become Python floats holding the
    same value, and int64 values become Python ints.
    """
    data = Path(path).read_bytes()
    meta = read_metadata(data)
    columns = {column.path: column for column in meta["columns"]}
    result: dict[str, list] = {}
    info: dict[str, dict] = {}
    for group in meta["row_groups"]:
        for chunk in group.get(1) or []:
            chunk_meta = chunk.get(3)
            if not isinstance(chunk_meta, dict):
                raise Malformed("parquet", "column chunk without metadata")
            path_in_schema = tuple(
                p.decode("utf-8") if isinstance(p, bytes) else str(p)
                for p in chunk_meta.get(3) or []
            )
            column = columns.get(path_in_schema)
            if column is None:
                raise Malformed("parquet", f"column chunk path {path_in_schema} not in schema")
            values, definitions, repetitions, chunk_info = _read_column_chunk(
                data, chunk_meta, column
            )
            rows = _assemble(column, values, definitions, repetitions)
            result.setdefault(column.name, []).extend(rows)
            existing = info.setdefault(
                column.name,
                {
                    "path": list(path_in_schema),
                    "physical": column.physical,
                    "max_definition": column.max_definition,
                    "max_repetition": column.max_repetition,
                    "chunks": 0,
                    "codec": chunk_info["codec"],
                    "encodings": set(),
                },
            )
            existing["chunks"] += 1
            existing["encodings"].update(chunk_info["encodings"])
    for entry in info.values():
        entry["encodings"] = sorted(entry["encodings"])
    for name, rows in result.items():
        if len(rows) != meta["num_rows"]:
            raise Malformed(
                "parquet", f"column {name} has {len(rows)} rows, file declares {meta['num_rows']}"
            )
    return {
        "columns": result,
        "num_rows": meta["num_rows"],
        "created_by": meta["created_by"],
        "column_info": info,
        "key_value_metadata": meta["key_value_metadata"],
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "reader": parse_identity(),
    }


# --- Minimal writer for synthetic fixtures ---------------------------------------------------


def _pack_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _pack_zigzag(value: int) -> bytes:
    return _pack_varint((value << 1) ^ (value >> 63))


class _Writer:
    """Thrift compact protocol encoder for the few structures a fixture needs."""

    def __init__(self) -> None:
        self.buf = bytearray()
        self.last: list[int] = [0]

    def begin_struct(self) -> None:
        self.last.append(0)

    def end_struct(self) -> None:
        self.buf.append(0)
        self.last.pop()

    def _field(self, field_id: int, kind: int) -> None:
        delta = field_id - self.last[-1]
        if 0 < delta < 16:
            self.buf.append((delta << 4) | kind)
        else:
            self.buf.append(kind)
            self.buf += _pack_zigzag(field_id)
        self.last[-1] = field_id

    def i32(self, field_id: int, value: int) -> None:
        self._field(field_id, _T_I32)
        self.buf += _pack_zigzag(value)

    def i64(self, field_id: int, value: int) -> None:
        self._field(field_id, _T_I64)
        self.buf += _pack_zigzag(value)

    def binary(self, field_id: int, value: bytes) -> None:
        self._field(field_id, _T_BINARY)
        self.buf += _pack_varint(len(value)) + value

    def begin_list(self, field_id: int, kind: int, size: int) -> None:
        self._field(field_id, _T_LIST)
        if size < 15:
            self.buf.append((size << 4) | kind)
        else:
            self.buf.append(0xF0 | kind)
            self.buf += _pack_varint(size)

    def struct_field(self, field_id: int) -> None:
        self._field(field_id, _T_STRUCT)
        self.begin_struct()


def _rle_levels(levels: list[int], bit_width: int) -> bytes:
    """Encode levels as one bit-packed run (fixtures are small)."""
    if bit_width == 0:
        return b""
    groups = (len(levels) + 7) // 8
    padded = levels + [0] * (groups * 8 - len(levels))
    bits = 0
    for index, level in enumerate(padded):
        bits |= level << (index * bit_width)
    raw = bits.to_bytes(groups * bit_width, "little")
    header = _pack_varint((groups << 1) | 1)
    return header + raw


def write_parquet_lowdim(
    path: Path,
    columns: dict[str, list],
    *,
    list_columns: tuple[str, ...] = (),
    physical: dict[str, str] | None = None,
) -> bytes:
    """Write flat FLOAT/INT64 columns and float LIST columns, PLAIN and uncompressed.

    Meant for synthetic control fixtures only. Every row must be present (no nulls) and
    list rows may be empty. Returns the bytes written.
    """
    physical = physical or {}
    names = list(columns)
    if not names:
        raise Malformed("parquet", "no columns to write")
    num_rows = len(columns[names[0]])
    if any(len(columns[n]) != num_rows for n in names):
        raise Malformed("parquet", "column lengths differ")
    body = bytearray(b"PAR1")
    chunks: list[dict] = []
    for name in names:
        rows = columns[name]
        is_list = name in list_columns
        kind = physical.get(
            name,
            "FLOAT"
            if is_list
            else (
                "INT64"
                if rows and isinstance(rows[0], int) and not isinstance(rows[0], bool)
                else "FLOAT"
            ),
        )
        code = {"FLOAT": "f", "INT64": "q", "DOUBLE": "d", "INT32": "i"}[kind]
        if is_list:
            definitions: list[int] = []
            repetitions: list[int] = []
            values: list = []
            for row in rows:
                if not row:
                    definitions.append(1)
                    repetitions.append(0)
                    continue
                for index, value in enumerate(row):
                    definitions.append(3)
                    repetitions.append(0 if index == 0 else 1)
                    values.append(value)
            page = struct.pack("<I", 0)  # placeholder replaced below
            rep_bytes = _rle_levels(repetitions, 1)
            def_bytes = _rle_levels(definitions, 2)
            page = (
                struct.pack("<I", len(rep_bytes))
                + rep_bytes
                + struct.pack("<I", len(def_bytes))
                + def_bytes
                + struct.pack(f"<{len(values)}{code}", *values)
            )
            num_values = len(definitions)
            max_def, max_rep = 3, 1
        else:
            definitions = [1] * num_rows
            def_bytes = _rle_levels(definitions, 1)
            page = (
                struct.pack("<I", len(def_bytes))
                + def_bytes
                + struct.pack(f"<{num_rows}{code}", *rows)
            )
            num_values = num_rows
            max_def, max_rep = 1, 0
        header = _Writer()
        header.begin_struct()
        header.i32(1, 0)  # DATA_PAGE
        header.i32(2, len(page))
        header.i32(3, len(page))
        header.struct_field(5)
        header.i32(1, num_values)
        header.i32(2, 0)  # PLAIN
        header.i32(3, 3)  # RLE definition levels
        header.i32(4, 3)  # RLE repetition levels
        header.end_struct()
        header.end_struct()
        offset = len(body)
        body += header.buf + page
        chunks.append(
            {
                "name": name,
                "path": [name, "list", "element"] if is_list else [name],
                "physical": {"FLOAT": 4, "INT64": 2, "DOUBLE": 5, "INT32": 1}[kind],
                "offset": offset,
                "size": len(header.buf) + len(page),
                "num_values": num_values,
                "list": is_list,
                "max_def": max_def,
                "max_rep": max_rep,
            }
        )
    meta = _Writer()
    meta.begin_struct()
    meta.i32(1, 2)  # version
    elements = 1 + sum(3 if c["list"] else 1 for c in chunks)
    meta.begin_list(2, _T_STRUCT, elements)
    meta.begin_struct()
    meta.binary(4, b"schema")
    meta.i32(5, len(chunks))
    meta.end_struct()
    for chunk in chunks:
        if chunk["list"]:
            meta.begin_struct()
            meta.i32(3, 1)  # OPTIONAL
            meta.binary(4, chunk["name"].encode())
            meta.i32(5, 1)
            meta.i32(6, 3)  # LIST converted type
            meta.end_struct()
            meta.begin_struct()
            meta.i32(3, 2)  # REPEATED
            meta.binary(4, b"list")
            meta.i32(5, 1)
            meta.end_struct()
            meta.begin_struct()
            meta.i32(1, chunk["physical"])
            meta.i32(3, 1)  # OPTIONAL
            meta.binary(4, b"element")
            meta.end_struct()
        else:
            meta.begin_struct()
            meta.i32(1, chunk["physical"])
            meta.i32(3, 1)  # OPTIONAL
            meta.binary(4, chunk["name"].encode())
            meta.end_struct()
    meta.i64(3, num_rows)
    meta.begin_list(4, _T_STRUCT, 1)
    meta.begin_struct()
    meta.begin_list(1, _T_STRUCT, len(chunks))
    for chunk in chunks:
        meta.begin_struct()
        meta.i64(2, chunk["offset"])
        meta.struct_field(3)
        meta.i32(1, chunk["physical"])
        meta.begin_list(2, _T_I32, 2)
        meta.buf += _pack_zigzag(0) + _pack_zigzag(3)
        meta.begin_list(3, _T_BINARY, len(chunk["path"]))
        for part in chunk["path"]:
            meta.buf += _pack_varint(len(part)) + part.encode()
        meta.i32(4, 0)  # UNCOMPRESSED
        meta.i64(5, chunk["num_values"])
        meta.i64(6, chunk["size"])
        meta.i64(7, chunk["size"])
        meta.i64(9, chunk["offset"])
        meta.end_struct()
        meta.end_struct()
    meta.i64(2, sum(c["size"] for c in chunks))
    meta.i64(3, num_rows)
    meta.end_struct()
    meta.binary(6, b"nisayon.evaluation.parquet_reader fixture writer")
    meta.end_struct()
    body += meta.buf + struct.pack("<I", len(meta.buf)) + b"PAR1"
    Path(path).write_bytes(bytes(body))
    return bytes(body)
