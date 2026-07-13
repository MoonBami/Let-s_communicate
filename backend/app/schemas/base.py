"""공용 스키마 베이스 — snake_case ↔ camelCase 계약 정합.

백엔드 내부는 Python 관례대로 snake_case 필드를 쓰되, JSON 입출력은
camelCase 로 맞춘다 → `packages/shared` 의 TypeScript 타입(camelCase)이
실제 API 계약과 1:1로 일치하게 된다.

- alias_generator=to_camel : 출력 시 camelCase 별칭 사용 (FastAPI 는 기본적으로
  response_model_by_alias=True 라 응답이 camelCase 로 나감).
- populate_by_name=True     : 입력은 camelCase(별칭)·snake_case(필드명) 둘 다 허용.
- from_attributes=True      : ORM 객체에서 바로 검증(model_validate) 가능.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        protected_namespaces=(),  # model_name 등 'model_' 필드 경고 방지
    )
