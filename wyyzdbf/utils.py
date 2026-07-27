import threading

from .exceptions import DBFRecordError


def decode_field(raw: bytes, encoding: str = "cp1252") -> str:
    """将 DBF 字段的原始字节解码为 Python `str`（去除填充空格与 NUL）。

    Raises
    ------
    DBFRecordError
        解码失败时包装抛出，保留原始异常信息。
    """
    try:
        return raw.rstrip(b"\x00 ").decode(encoding)
    except UnicodeDecodeError as exc:
        raise DBFRecordError(
            f"字段解码失败（encoding={encoding}）: {exc}"
        ) from exc


def encode_field(value: str, length: int, encoding: str = "cp1252") -> bytes:
    """把字符串按指定编码写入 DBF，长度必须不超过字段定义的 `length`。

    超长会抛出 `DBFRecordError`，防止文件结构损坏。
    DBF 字段用空格填充，不使用 NUL 结束符。
    """
    encoded = value.encode(encoding)
    if len(encoded) > length:
        raise DBFRecordError(
            f"字段值长度 ({len(encoded)}) 超出定义 ({length})"
        )
    return encoded.ljust(length, b" ")


def get_lock() -> threading.Lock:
    """返回一个进程级别的全局锁，用于并发写入保护。"""
    if not hasattr(get_lock, "_lock"):
        get_lock._lock = threading.Lock()
    return get_lock._lock