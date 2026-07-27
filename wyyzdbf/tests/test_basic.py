import os
import struct
import tempfile
import pytest

from wyyzdbf import DBFWriter, DBFReader, DBFHeaderError, DBFRecordError
from wyyzdbf.writer import DBFFieldDesc


def test_roundtrip():
    fields = [DBFFieldDesc("NAME", "C", 20), DBFFieldDesc("AGE", "N", 3, 0)]
    rows = [("Alice", 30), ("Bob", 25)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields) as wtr:
            for r in rows:
                wtr.append(r)
        with DBFReader(tmp) as rdr:
            parsed = list(rdr)
        assert len(parsed) == 2
        assert parsed[0]["NAME"] == "Alice"
        assert parsed[0]["AGE"] == 30
        assert parsed[1]["NAME"] == "Bob"
        assert parsed[1]["AGE"] == 25
    finally:
        os.unlink(tmp)


def test_header_values():
    fields = [DBFFieldDesc("X", "C", 10)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields) as wtr:
            wtr.append(["hello"])
            wtr.append(["world"])
        with open(tmp, "rb") as f:
            raw = f.read(32)
        version, y, m, d, rec_cnt, hdr_len, rec_len = \
            struct.Struct("<BBBBIHH20x").unpack(raw)
        assert version == 0x03
        assert rec_cnt == 2
        assert hdr_len == 32 + 1 * 32 + 1
        assert rec_len == 1 + 10
    finally:
        os.unlink(tmp)


def test_custom_encoding():
    fields = [DBFFieldDesc("NAME", "C", 20)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields, encoding="utf-8") as wtr:
            wtr.append(["中文名"])
        with DBFReader(tmp, encoding="utf-8") as rdr:
            recs = list(rdr)
        assert recs[0]["NAME"] == "中文名"
    finally:
        os.unlink(tmp)


def test_delete_mark():
    fields = [DBFFieldDesc("V", "C", 5)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields) as wtr:
            wtr.append(["a"])
            wtr.append(["b"])
        hdr_len = 32 + 1 * 32 + 1
        with open(tmp, "r+b") as f:
            f.seek(hdr_len + 1 + 5)
            f.write(b"*")
        with DBFReader(tmp) as rdr:
            recs = list(rdr)
        assert len(recs) == 1
        assert recs[0]["V"] == "a"
    finally:
        os.unlink(tmp)


def test_value_count_mismatch():
    fields = [DBFFieldDesc("A", "C", 5), DBFFieldDesc("B", "C", 5)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields) as wtr:
            with pytest.raises(DBFRecordError):
                wtr.append(["only_one"])
    finally:
        os.unlink(tmp)


def test_empty_file():
    fields = [DBFFieldDesc("X", "C", 5)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields):
            pass
        with DBFReader(tmp) as rdr:
            assert rdr.header.record_count == 0
            assert list(rdr) == []
    finally:
        os.unlink(tmp)


def test_numeric_types():
    fields = [
        DBFFieldDesc("INTV", "N", 5, 0),
        DBFFieldDesc("DECV", "N", 8, 2),
    ]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields) as wtr:
            wtr.append([42, 3.14])
            wtr.append([-1, 0.00])
        with DBFReader(tmp) as rdr:
            recs = list(rdr)
        assert recs[0]["INTV"] == 42
        assert recs[0]["DECV"] == pytest.approx(3.14, 0.01)
        assert recs[1]["INTV"] == -1
        assert recs[1]["DECV"] == pytest.approx(0.0, 0.01)
    finally:
        os.unlink(tmp)


def test_float_field_type():
    fields = [DBFFieldDesc("FVAL", "F", 10, 3)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields) as wtr:
            wtr.append([123.456])
        with DBFReader(tmp) as rdr:
            recs = list(rdr)
        assert recs[0]["FVAL"] == 123.456
    finally:
        os.unlink(tmp)


def test_logical_field():
    fields = [DBFFieldDesc("FLAG", "L", 1)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields) as wtr:
            wtr.append(["Y"])
            wtr.append(["N"])
            wtr.append(["T"])
            wtr.append(["F"])
        with DBFReader(tmp) as rdr:
            recs = list(rdr)
        assert recs[0]["FLAG"] is True
        assert recs[1]["FLAG"] is False
        assert recs[2]["FLAG"] is True
        assert recs[3]["FLAG"] is False
    finally:
        os.unlink(tmp)


def test_date_field():
    fields = [DBFFieldDesc("DATE", "D", 8)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields) as wtr:
            wtr.append(["20260727"])
            wtr.append(["20000101"])
        with DBFReader(tmp) as rdr:
            recs = list(rdr)
        assert recs[0]["DATE"] == "2026-07-27"
        assert recs[1]["DATE"] == "2000-01-01"
    finally:
        os.unlink(tmp)


def test_many_records():
    fields = [DBFFieldDesc("SEQ", "N", 6, 0)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        count = 500
        with DBFWriter(tmp, fields) as wtr:
            for i in range(count):
                wtr.append([i])
        with DBFReader(tmp) as rdr:
            recs = list(rdr)
        assert len(recs) == count
        for i, rec in enumerate(recs):
            assert rec["SEQ"] == i
    finally:
        os.unlink(tmp)


def test_field_name_too_long():
    with pytest.raises(DBFHeaderError):
        DBFFieldDesc("A" * 11, "C", 10)


def test_long_value_truncation():
    fields = [DBFFieldDesc("NAME", "C", 5)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields) as wtr:
            with pytest.raises(DBFRecordError):
                wtr.append(["toolong"])
    finally:
        os.unlink(tmp)


def test_context_manager_reentry():
    fields = [DBFFieldDesc("X", "C", 5)]
    with tempfile.NamedTemporaryFile(suffix=".dbf", delete=False) as tf:
        tmp = tf.name
    try:
        with DBFWriter(tmp, fields) as wtr:
            wtr.append(["a"])
        with DBFWriter(tmp, fields) as wtr:
            wtr.append(["b"])
        with DBFReader(tmp) as rdr:
            recs = list(rdr)
        assert len(recs) == 1
        assert recs[0]["X"] == "b"
    finally:
        os.unlink(tmp)