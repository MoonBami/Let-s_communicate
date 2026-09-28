"""학교·학생 입력 정규화 — DB 없이 도는 단위 테스트."""

import pytest

from app.services.directory import normalize_class_name, normalize_school_code, normalize_student_name


@pytest.mark.parametrize(
    "raw, expected",
    [("demo001", "DEMO001"), ("  7010057 ", "7010057"), ("ab", None), ("DEMO 001", None), ("", None), ("x/y", None)],
)
def test_학교_코드_정규화(raw, expected):
    assert normalize_school_code(raw) == expected


@pytest.mark.parametrize(
    "raw, expected", [("2반", "2"), (" 2 ", "2"), ("2", "2"), ("반", "반"), ("햇살반", "햇살"), ("1 0반", "10")]
)
def test_반_정규화(raw, expected):
    assert normalize_class_name(raw) == expected


def test_이름_공백_정리():
    assert normalize_student_name("  김  학생 ") == "김 학생"
