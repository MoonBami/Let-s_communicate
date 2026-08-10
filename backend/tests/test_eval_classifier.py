"""평가 하네스의 지표 계산 검증.

지표가 틀리면 모델이 좋아졌는지 나빠졌는지를 잘못 판단한다. 특히 '치명 오류'
집계가 틀리면 위험한 모델을 안전하다고 읽는다. 손으로 계산할 수 있는 작은
예시로 고정한다.
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "eval_classifier.py"


def _load():
    spec = importlib.util.spec_from_file_location("eval_classifier", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ev = _load()


# --- 정확도 -----------------------------------------------------------------


def test_정확도_전부_맞음():
    assert ev.accuracy([("grades", "grades"), ("life", "life")]) == 1.0


def test_정확도_절반():
    assert ev.accuracy([("grades", "grades"), ("life", "other")]) == 0.5


def test_정확도_빈_입력은_0():
    assert ev.accuracy([]) == 0.0


# --- 카테고리별 지표 --------------------------------------------------------


def test_완벽한_예측의_지표():
    pairs = [("grades", "grades")] * 3
    m = ev.per_class_metrics(pairs)["grades"]
    assert (m["precision"], m["recall"], m["f1"], m["support"]) == (1.0, 1.0, 1.0, 3.0)


def test_과잉예측은_정밀도를_깎는다():
    # grades 2건이 정답인데 3건을 grades 로 예측 (life 1건을 잘못 넣음)
    pairs = [("grades", "grades"), ("grades", "grades"), ("life", "grades")]
    m = ev.per_class_metrics(pairs)
    assert m["grades"]["precision"] == pytest.approx(2 / 3)
    assert m["grades"]["recall"] == 1.0
    assert m["life"]["recall"] == 0.0


def test_누락은_재현율을_깎는다():
    pairs = [("grades", "grades"), ("grades", "other")]
    m = ev.per_class_metrics(pairs)
    assert m["grades"]["recall"] == 0.5
    assert m["grades"]["precision"] == 1.0


def test_한번도_예측되지_않은_카테고리는_0():
    m = ev.per_class_metrics([("grades", "grades")])["violence_dispute"]
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["support"] == 0.0


def test_macro_f1은_평가셋에_없는_라벨을_제외한다():
    """support 0 인 카테고리를 평균에 넣으면 점수가 부당하게 깎인다."""
    pairs = [("grades", "grades")]
    assert ev.macro_f1(ev.per_class_metrics(pairs)) == 1.0


# --- 혼동행렬 ---------------------------------------------------------------


def test_혼동행렬_집계():
    pairs = [("grades", "grades"), ("grades", "other"), ("grades", "other")]
    matrix = ev.confusion(pairs)
    assert matrix[("grades", "grades")] == 1
    assert matrix[("grades", "other")] == 2


# --- 치명 오류 (가장 중요) --------------------------------------------------


def test_치명오류_학폭이_행정으로():
    pairs = [("violence_dispute", "administrative")]
    assert ev.critical_errors(pairs) == pairs


def test_치명오류가_아닌_경우():
    """학폭을 '생활'로 틀린 것은 교사에게는 가므로 치명 오류가 아니다."""
    assert ev.critical_errors([("violence_dispute", "life")]) == []


def test_행정을_학폭으로_틀린_것은_치명오류가_아니다():
    """반대 방향 오류는 교사가 한 번 더 보는 것으로 끝난다."""
    assert ev.critical_errors([("administrative", "violence_dispute")]) == []


def test_정상_예측은_치명오류가_아니다():
    assert ev.critical_errors([("violence_dispute", "violence_dispute")]) == []


def test_치명오류_집계는_민감라벨만_센다():
    pairs = [
        ("violence_dispute", "administrative"),   # 치명
        ("grades", "administrative"),             # 일반 오류
        ("learning", "administrative"),           # 일반 오류
    ]
    assert len(ev.critical_errors(pairs)) == 1


def test_자동응대_카테고리와_민감라벨_설정이_유효하다():
    from app.services.ai.classifier import CATEGORIES
    from app.services.ai.gate import AUTO_ANSWER_CATEGORY as GATE_CATEGORY

    assert ev.AUTO_ANSWER_CATEGORY == GATE_CATEGORY, (
        "게이트가 자동 응대하는 카테고리와 평가 기준이 어긋나면 잘못된 지표가 나온다"
    )
    assert set(ev.SENSITIVE_TRUE) <= set(CATEGORIES)
