"""Test encoding decisions at the file and detector boundaries."""

import codecs
from pathlib import Path
from unittest.mock import patch

import pytest

from sqlfluff.core.helpers.file import get_encoding

SQL = "SELECT 'Привіт, Žilina' AS greeting;\n"


@pytest.mark.parametrize(
    "codec,bom,expected",
    [
        pytest.param("utf-32-le", codecs.BOM_UTF32_LE, "utf-32", id="utf32-le"),
        pytest.param("utf-32-be", codecs.BOM_UTF32_BE, "utf-32", id="utf32-be"),
        pytest.param("utf-16-le", codecs.BOM_UTF16_LE, "utf-16", id="utf16-le"),
        pytest.param("utf-16-be", codecs.BOM_UTF16_BE, "utf-16", id="utf16-be"),
        pytest.param("utf-8", codecs.BOM_UTF8, "utf-8-sig", id="utf8-bom"),
    ],
)
def test_get_encoding_bom_preserves_sql(
    tmp_path: Path, codec: str, bom: bytes, expected: str
) -> None:
    """A BOM must select a codec that decodes the complete SQL without its BOM."""
    sql_path = tmp_path / "query.sql"
    sql_path.write_bytes(bom + SQL.encode(codec))

    with patch("sqlfluff.core.helpers.file.chardet.detect") as detector:
        encoding = get_encoding(str(sql_path))

    detector.assert_not_called()
    assert encoding == expected
    assert sql_path.read_text(encoding=encoding) == SQL


@pytest.mark.parametrize("encoding", ["utf-8", "cp1251"])
def test_get_encoding_explicit_codec_skips_file_access(
    tmp_path: Path, encoding: str
) -> None:
    """An explicit encoding must be usable before the input file exists."""
    missing_path = tmp_path / "not-created.sql"

    with patch("builtins.open") as open_file:
        assert get_encoding(str(missing_path), config_encoding=encoding) == encoding

    open_file.assert_not_called()


def test_get_encoding_empty_file_skips_detector(tmp_path: Path) -> None:
    """An empty SQL file must select an encoding without consulting the detector."""
    sql_path = tmp_path / "empty.sql"
    sql_path.write_bytes(b"")

    with patch("sqlfluff.core.helpers.file.chardet.detect") as detector:
        encoding = get_encoding(str(sql_path))

    detector.assert_not_called()
    assert encoding == "ascii"
    assert sql_path.read_text(encoding=encoding) == ""


def test_get_encoding_passes_complete_non_ascii_input_to_detector(
    tmp_path: Path,
) -> None:
    """Delegate BOM-less Unicode input intact and return the detector's codec."""
    sql_path = tmp_path / "unicode.sql"
    payload = SQL.encode("utf-8")
    sql_path.write_bytes(payload)

    with patch(
        "sqlfluff.core.helpers.file.chardet.detect",
        return_value={"encoding": "utf-8"},
    ) as detector:
        encoding = get_encoding(str(sql_path))

    detector.assert_called_once_with(payload)
    assert encoding == "utf-8"
    assert sql_path.read_text(encoding=encoding) == SQL
