"""F5: 유사 사례 검색(RAG).

`complaint_cases` 를 pgvector 코사인 거리로 검색해 과거 대응 사례를 찾고,
답변 초안(F4) 프롬프트에 근거로 주입한다.

검색은 **같은 임베딩 모델로 만든 벡터끼리만** 비교한다(모델이 다르면 벡터
공간이 달라 유사도가 무의미해짐).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import CaseEmbedding, ComplaintCase
from app.services.ai.embedding import embed

# 이 값 미만은 '관련 없음'으로 보고 초안 프롬프트에 넣지 않는다.
# 무관한 사례가 섞이면 초안 품질이 오히려 떨어지기 때문.
MIN_SIMILARITY = 0.2


@dataclass
class SimilarCase:
    case_id: uuid.UUID
    category: str | None
    summary: str
    resolution: str
    similarity: float

    def as_prompt_line(self) -> str:
        return f"{self.summary} → 대응: {self.resolution}"


def index_case(db: Session, case: ComplaintCase) -> str:
    """사례 임베딩을 생성·저장(있으면 갱신)하고 사용한 모델명을 돌려준다."""
    vector, model_name = embed(f"{case.summary}\n{case.resolution}")

    row = db.get(CaseEmbedding, case.id)
    if row is None:
        row = CaseEmbedding(case_id=case.id)
        db.add(row)
    row.embedding = vector
    row.model_name = model_name
    return model_name


def search_similar_cases(
    db: Session,
    text: str,
    limit: int = 3,
    category: str | None = None,
) -> list[SimilarCase]:
    vector, model_name = embed(text)
    distance = CaseEmbedding.embedding.cosine_distance(vector)

    stmt = (
        select(ComplaintCase, distance.label("distance"))
        .join(CaseEmbedding, CaseEmbedding.case_id == ComplaintCase.id)
        .where(CaseEmbedding.model_name == model_name)
    )
    if category is not None:
        stmt = stmt.where(ComplaintCase.category == category)

    rows = db.execute(stmt.order_by(distance).limit(limit)).all()

    results = []
    for case, dist in rows:
        similarity = 1.0 - float(dist)
        if similarity < MIN_SIMILARITY:
            continue
        results.append(
            SimilarCase(
                case_id=case.id,
                category=case.category,
                summary=case.summary,
                resolution=case.resolution,
                similarity=round(similarity, 4),
            )
        )
    return results
