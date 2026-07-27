import struct
import datetime
from dataclasses import dataclass, field
from typing import BinaryIO, List, Sequence

from .exceptions import DBFHeaderError, DBFRecordError
from .utils import encode_field, get_lock


@dataclass
class DBFHeader:
    version: int = 0x03
    last_update: bytes = field(default_factory=lambda: bytes([
        datetime.datetime.now().year - 1900,
        datetime.datetime.now().month,
        datetime.datetime.now().day,
    ]))
    record_count: int = 0
    header_length: int = 0
    record_length: int = 0
    fields: List = field(default_factory=list)

    def compute_lengths(self) -> None:
        self.header_length = 32 + len(self.fields) * 32 + 1
        self.record_length = 1 + sum(f.length for f in self.fields)


@dataclass
class DBFFieldDesc:
    name: str
    type: str
    length: int
    decimal: int = 0

    _MAX_NAME_LENGTH = 10

    def __post_init__(self):            # <-- 创建时立即校验，不等到写入才报错
        if len(self.name) > self._MAX_NAME_LENGTH:
            raise DBFHeaderError(
                f"Field name '{self.name}' exceeds {self._MAX_NAME_LENGTH} byte limit"
            )

    def to_bytes(self, encoding: str = "cp1252") -> bytes:
        if len(self.name) > self._MAX_NAME_LENGTH:
            raise DBFHeaderError(
                f"Field name '{self.name}' exceeds {self._MAX_NAME_LENGTH} byte limit"
            )
        name_bytes = self.name.encode(encoding)[:self._MAX_NAME_LENGTH]
        name_padded = name_bytes.ljust(11, b"\x00")

        desc = bytearray(32)
        desc[0:11] = name_padded
        desc[11] = ord(self.type)
        desc[16] = self.length
        desc[17] = self.decimal
        return bytes(desc)


HEADER_STRUCT = struct.Struct("<BBBBIHH20x")


def _pack_header(version: int, last_update: bytes, record_count: int,
                 header_length: int, record_length: int) -> bytes:
    """Pack DBF header (first 32 bytes). last_update is 3 raw bytes."""
    if len(last_update) < 3:
        last_update = b"\x00\x00\x00"
    return HEADER_STRUCT.pack(
        version,
        last_update[0],
        last_update[1],
        last_update[2],
        record_count,
        header_length,
        record_length,
    )


class DBFWriter:
    """DBF file writer. Writes header on enter, records via append().

    Usage:
        fields = [
            DBFFieldDesc('NAME', 'C', 30),
            DBFFieldDesc('AGE',  'N',  3, 0),
        ]
        with DBFWriter('output.dbf', fields) as wtr:
            wtr.append(["Alice", 30])
            wtr.append(["Bob", 25])
    """

    def __init__(
        self,
        path: str,
        fields: Sequence[DBFFieldDesc],
        encoding: str = "cp1252",
    ):
        self.path = path
        self.fields = list(fields)
        self.encoding = encoding
        self._fp: BinaryIO | None = None
        self._header = DBFHeader(fields=self.fields)
        self._header.compute_lengths()

    def __enter__(self) -> "DBFWriter":
        self._fp = open(self.path, "wb")
        self._write_header()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._fp is None:
            return False
        if exc_type is None:
            self._finalize()
        self._fp.close()
        self._fp = None
        return False

    def _write_header(self) -> None:
        if self._fp is None:
            raise DBFRecordError("Writer not used in context")
        self._header.compute_lengths()
        buf = _pack_header(
            version=self._header.version,
            last_update=self._header.last_update,
            record_count=self._header.record_count,
            header_length=self._header.header_length,
            record_length=self._header.record_length,
        )
        self._fp.write(buf)
        for fd in self.fields:
            self._fp.write(fd.to_bytes(self.encoding))
        self._fp.write(b"\x0D")

    def append(self, values: Sequence) -> None:
        if self._fp is None:
            raise DBFRecordError("Writer not used in context")
        if len(values) != len(self.fields):
            raise DBFRecordError(
                f"Value count ({len(values)}) != field count ({len(self.fields)})"
            )

        lock = get_lock()
        with lock:
            self._fp.write(b" ")
            for i, fd in enumerate(self.fields):
                v = values[i]
                raw = encode_field(str(v) if v is not None else "",
                                   fd.length, self.encoding)
                self._fp.write(raw)
            self._header.record_count += 1

    def _finalize(self) -> None:
        if self._fp is None:
            return
        saved = self._fp.tell()
        self._fp.seek(4)
        self._fp.write(struct.pack("<I", self._header.record_count))
        self._fp.seek(saved)