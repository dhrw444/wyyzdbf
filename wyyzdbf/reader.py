import struct
from dataclasses import dataclass, field
from datetime import datetime
from typing import BinaryIO, Iterator, List, Tuple

from .exceptions import DBFHeaderError, DBFRecordError
from .utils import decode_field


@dataclass
class DBFFieldDesc:
    name: str
    type: str
    length: int
    decimal: int

    @staticmethod
    def from_bytes(raw: bytes, encoding: str = "cp1252") -> "DBFFieldDesc":
        name = decode_field(raw[0:11], encoding)
        ftype = raw[11:12].decode("ascii")
        length = raw[16]
        decimal = raw[17]
        return DBFFieldDesc(name, ftype, length, decimal)


@dataclass
class DBFHeader:
    version: int = 0x03
    last_update: Tuple[int, int, int] = field(default_factory=lambda: (
        datetime.now().year,
        datetime.now().month,
        datetime.now().day,
    ))
    record_count: int = 0
    header_length: int = 0
    record_length: int = 0
    fields: List[DBFFieldDesc] = field(default_factory=list)


class DBFReader:
    """Read-only context-managed DBF reader.

    Usage:
        with DBFReader('file.dbf') as rdr:
            for rec in rdr:
                print(rec)
    """

    HEADER_STRUCT = struct.Struct("<BBBBIHH20x")

    def __init__(self, path: str, encoding: str = "cp1252"):
        self.path = path
        self.encoding = encoding
        self._fp: BinaryIO | None = None
        self.header: DBFHeader | None = None

    def __enter__(self) -> "DBFReader":
        self._fp = open(self.path, "rb")
        self.header = self._read_header()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._fp:
            self._fp.close()
        return False

    def _read_header(self) -> DBFHeader:
        try:
            raw = self._fp.read(self.HEADER_STRUCT.size)
            if len(raw) != self.HEADER_STRUCT.size:
                raise DBFHeaderError("File too short for DBF header")

            version, y, month, day, record_count, header_len, record_len = \
                self.HEADER_STRUCT.unpack(raw)

            fields: list[DBFFieldDesc] = []
            desc_area = header_len - self.HEADER_STRUCT.size - 1
            if desc_area > 0 and desc_area % 32 == 0:
                for _ in range(desc_area // 32):
                    desc_raw = self._fp.read(32)
                    if len(desc_raw) < 32 or desc_raw[0] == 0x0D:
                        break
                    fields.append(DBFFieldDesc.from_bytes(desc_raw, self.encoding))
            # skip terminator
            self._fp.read(1)

            return DBFHeader(
                version=version,
                last_update=(y + 1900, month, day),
                record_count=record_count,
                header_length=header_len,
                record_length=record_len,
                fields=fields,
            )
        except struct.error as exc:
            raise DBFHeaderError(f"Header struct unpack error: {exc}") from exc

    def __iter__(self) -> Iterator[dict]:
        if self._fp is None or self.header is None:
            raise DBFRecordError("Reader not used in context or header not loaded")

        for _ in range(self.header.record_count):
            raw = self._fp.read(self.header.record_length)
            if len(raw) < self.header.record_length:
                break
            rec = self._parse_record(raw)
            if rec is not None:
                yield rec

    def _parse_record(self, raw: bytes) -> dict | None:
        if not raw:
            return None
        if raw[0:1] == b"*":
            return None

        pos = 1
        result = {}
        for fd in self.header.fields:
            raw_val = raw[pos : pos + fd.length]
            pos += fd.length
            value = decode_field(raw_val, self.encoding)

            if fd.type in ("N", "F"):
                stripped = value.strip()
                try:
                    value = float(stripped) if fd.decimal else int(stripped)
                except ValueError:
                    value = None
            elif fd.type == "D":
                try:
                    y = int(value[0:4]); m = int(value[4:6]); d = int(value[6:8])
                    value = f"{y:04d}-{m:02d}-{d:02d}"
                except Exception:
                    value = None
            elif fd.type == "L":
                value = value.strip().upper() in ("Y", "T", "1")

            result[fd.name] = value

        return result