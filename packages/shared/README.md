# @sotong/shared — 공용 계약

웹·(추후)모바일·백엔드가 공유하는 **타입·ENUM·API 경로의 단일 소스**.
여기 정의가 프론트/백엔드 계약의 기준이 됩니다.

## 내용

| 파일 | 역할 |
|------|------|
| `src/enums.ts` | `db/schema.sql`의 PostgreSQL ENUM과 1:1 대응 상수 + 한국어 라벨 |
| `src/types.ts` | 도메인 DTO (User, Complaint, Classification, AnswerDraft 등) |
| `src/api-paths.ts` | API 경로 상수 (프론트/백엔드가 같은 문자열 참조) |
| `src/index.ts` | 배럴 export |

## 사용

```ts
import { API, CATEGORY_LABEL, type Complaint } from '@sotong/shared';
```

빌드 없이 소스(`src`)를 직접 참조합니다 (`main`/`types`가 `.ts`를 가리킴).
Vite alias와 tsconfig paths로 연결되어 있어 별도 빌드 단계가 필요 없습니다.

## 🐫 네이밍 규칙 (camelCase)

이 패키지의 DTO 필드는 **camelCase**(`schoolId`, `accessToken`)입니다.
백엔드(FastAPI)는 내부적으로 snake_case를 쓰지만, 응답/요청 JSON은 camelCase로
주고받도록 맞춰져 있습니다(`backend/app/schemas/base.py`의 `CamelModel`).
따라서 **여기 타입이 실제 API JSON과 1:1로 일치**합니다.

## ⚠️ 유지보수

`db/schema.sql`의 ENUM/컬럼을 바꾸면 **`enums.ts`·`types.ts`도 함께 갱신**하세요.
스키마와 이 패키지가 어긋나면 프론트/백엔드 계약이 깨집니다.
