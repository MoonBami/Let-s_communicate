# 「소통해요」 개발 현황

> 기준일: **2026-08-06** · 브랜치: `JonghoonBranch`
> 기획·의사결정 배경은 [`project-overview.md`](project-overview.md), 실행 방법은
> [루트 README](../README.md) / [backend README](../backend/README.md) 참고.
> 이 문서는 **무엇이 실제로 동작하는지와 어디까지 검증됐는지**를 구분해 적는다.

---

## 1. 한 줄 요약

**게이트웨이 파이프라인이 접수부터 종결까지 엔드투엔드로 동작한다.**
Phase 1 MVP(F1·F4·F9) + Phase 2(F2·F3·F5·F8)가 코드·런타임 양쪽으로 닫혔고,
F7은 변환 파이프라인만, F6은 미착수.

단, **AI가 실제 Claude API로 돌아간 적은 아직 없다.** 지금까지 검증된 것은 전부
규칙 기반 fallback 경로다. (F3 욕설 필터는 애초에 규칙 기반이 최종 경로라 예외)

---

## 2. 검증 수준 범례

기능이 "된다"는 말은 검증 수준에 따라 의미가 다르므로 구분해 표기한다.

| 표기 | 의미 |
|------|------|
| 🟢 런타임 | 실제로 DB·서버를 띄우고 요청을 보내 결과를 확인함 |
| 🟡 부분 | 일부 경로만 확인. 미확인 경로를 명시함 |
| ⚪ 정적 | 문법·타입 검사만 통과. 실행해 본 적 없음 |
| ⛔ 미착수 | 코드 없음 |

---

## 3. 기능별 상태 (F1~F9)

| 기능 | 상태 | 검증 | 비고 |
|------|------|------|------|
| **F1** 민원 자동 분류·라우팅 | 동작 | 🟡 | fallback(키워드) 경로만 확인. Claude 경로 미확인 |
| **F2** 감정·위험 탐지 | 동작 | 🟡 | fallback(휴리스틱) 경로만 확인 |
| **F3** 욕설·위협 필터·증거 | 동작 | 🟢 | 규칙 기반이 최종 경로이므로 완전 검증 |
| **F4** 공식 답변 초안 | 동작 | 🟡 | 템플릿 fallback만 확인. 표준 문장 템플릿 미구현(§6-4) |
| **F5** 유사 사례 검색(RAG) | 동작 | 🟡 | 해싱 임베딩만 확인. 외부 임베딩 API 미확인 |
| **F6** 안심번호·예약 상담 | 미착수 | ⛔ | 통신사/제3자 사업자 계약 선행 필요 |
| **F7** 실시간 녹음·STT | 가드만 | 🟡 | **실패 경로만** 확인. 성공 변환 미확인(자격증명 없음) |
| **F8** MDT 이관 | 동작 | 🟢 | 상태 전이 전부 확인 |
| **F9** 관리자 통계 대시보드 | 동작 | 🟢 | 실제 집계 확인 |
| — 인증·권한 가드 | 동작 | 🟢 | 역할별 10건 확인 |

---

## 4. 계층별 현황

| 계층 | 구현됨 | 안 된 것 |
|------|--------|----------|
| **접수** | 웹 폼(로그인 불필요) | 채팅·통화 채널(ENUM에만 존재), 학부모 본인 확인 |
| **AI 처리** | F3→F1→F2→라우팅 동기 파이프라인, 이력·증거 영속화 | 비동기화(현재 접수 응답이 AI 호출을 기다림) |
| **교사** | 민원함(필터 통과분·본인 배정분), 상세(분석·유사사례·초안·이관) | 초안 채택/수정 저장, 답변 발송 |
| **관리** | 이관 관리, 대시보드, 증거 열람(admin·mdt) | 감사 로그, 수동 재배정, 통계 상세 |
| **비동기** | Celery 워커 3개 태스크 + beat 1건 | 알림 발송, 배치 재분석 |

### 접수 파이프라인 분기

| 결과 | `complaints.status` | 처리 |
|------|---------------------|------|
| 욕설·위협 감지 | `filtered_blocked` | 교사 미노출, 원문을 `content_filter_logs.raw_evidence`로 증거 보관 |
| 단순 행정 | `auto_answered` | 챗봇 자동 응대 후보 (**실제 응대 문구는 미생성** — §6-2) |
| 그 외 정당한 민원 | `pending_teacher` | `teacher_assignments` 기반 담당 교사 자동 배정 |

### F8 이관 상태 전이

| 처리 | `escalations.status` | `complaints.status` |
|------|----------------------|---------------------|
| 요청 | `requested` | `escalated` |
| 접수 | `accepted` | (유지) |
| 해결 | `resolved` | `closed` + `closed_at` |
| 반송 | `rejected` | `pending_teacher` (교사에게 복귀) |

---

## 5. 검증 기록 (2026-08-06)

로컬에서 실제로 띄워 확인한 내용. 재현 절차는 [backend README](../backend/README.md) 참고.

**환경**: Docker(PostgreSQL 16 + pgvector, Redis 7) + Python 3.12 컨테이너.
API 키 없음 → 전 구간 fallback 경로.

### API — 35건 통과 / 0건 실패

- **접수 파이프라인**: 정당한 민원 → `pending_teacher` + 교사 자동 배정 /
  단순 행정 → `auto_answered` / 욕설·위협 → `filtered_blocked` + `critical`
- **권한 가드 10건**: 학부모 민원함 차단(403), 교사 대시보드 차단(403),
  교사가 차단 민원 열람 차단(403)·admin은 허용(200), 사례 등록·이관 목록 차단, 미인증(401)
- **F5 pgvector 검색**: "수행평가 점수 산정 기준" 민원에 시드 사례가 유사도 **0.32**로 매칭,
  카테고리 필터 일치
- **F8 상태 전이 전부**: 요청→`escalated`, 중복 요청 409, 잘못된 status 400,
  접수→해결→`closed`+`closed_at`, 종결 재처리 409, 반송→`pending_teacher` 복귀

### Celery 워커 — 17건 통과 / 0건 실패

`.delay()` 로 실제 브로커를 경유해 워커가 실행한 결과를 확인.

- 태스크 3개 등록 + beat 스케줄(`crontab: 0 4 * * *`) 확인
- `index_case_embedding`: 임베딩 삭제 후 재생성 → `hash-embed-v1`, **벡터 차원 1536**
  (스키마의 `VECTOR(1536)`과 일치)
- `reindex_missing_case_embeddings`: 누락 3건 → 3건 처리 → 누락 0건,
  **재실행 시 0건(멱등)**
- beat 디스패치: 주기를 5초로 덮어쓴 래퍼로 실제 발화 확인 (첫 발화 1건 처리, 다음 0건)
- `transcribe_recording` 가드 3개: 없는 녹음 → `ValueError` /
  `consent_given=false` → `ValueError`(통신비밀보호법) / 동의 있음 + STT 미설정 → `RuntimeError`.
  **세 경우 모두 대화록 레코드 미생성** (빈 대화록이 '아무 말도 없었다'로 오해되지 않도록)

### 프론트엔드

- `tsc --noEmit` 통과 (shared + web), `vite build` 성공 (번들 726KB — §6-7)
- 브라우저 확인: 교사 로그인 → 네비에 "민원함"만 노출 → 상세에서 F1·F2 분석 +
  F5 유사 사례 + 초안 생성(즉시 이력 반영) + 이관 폼 정상
- MDT 로그인 → 네비 3개 노출, 이관 관리에서 "접수" 클릭 → `이관 요청`→`접수됨` 전환,
  종결 건엔 액션 버튼 없음
- 대시보드가 데모 데이터가 아닌 **실제 집계** 표시
- 교사로 `/escalations` 직접 접근 → "접근 권한이 없습니다", 콘솔 에러 0건

### 검증되지 않은 것

- **Claude API 경로 전체** (F1 분류, F2 위험, F4 초안) — 키 없이 fallback만 확인
- **외부 임베딩 API 경로** (F5) — 해싱 fallback만 확인
- **STT 성공 변환** (F7) — CLOVA 자격증명 없음. 응답 파싱·화자 분리 미확인
- 동시성·부하, 대량 데이터에서의 pgvector 검색 성능

---

## 6. 알려진 갭

### 6-1. 리포에 테스트가 없다 ⚠️ 최우선

위 52건 검증은 일회성 스크립트로 수행했고 리포에 커밋되지 않았다.
코드를 고쳤을 때 회귀를 잡을 방법이 없다.

특히 **F3 욕설 필터는 오차단이 곧 사고**(정당한 민원이 교사에게 안 감)인데
회귀 테스트가 없다. 필터 패턴을 건드리는 순간 위험해진다.

### 6-2. 챗봇 자동 응대가 실체가 없다

단순 행정 민원이 `auto_answered` 상태만 기록되고 **응대 문구가 어디에도 남지 않는다.**
`complaint_messages` 테이블은 스키마에 있으나 ORM 모델조차 없다.

결과적으로 학부모 입장에서는 "자동 응대 완료"인데 답을 받지 못한다.
F1 기획("단순 행정은 챗봇 자동 응대")과 실제 동작이 어긋나 있다.

### 6-3. 학부모가 자기 민원을 조회할 수 없다

접수 API(`POST /api/complaints`)가 `parentId`를 받지 않고 `complaints.parent_id`를
채우지 않는다 → 사실상 익명 접수.

학부모 계정으로 로그인은 되지만 민원함은 403이므로 **로그인 후 갈 곳이 없다.**
`guardianships`(보호자-학생 관계) 테이블도 미사용.

### 6-4. F4 표준 문장 템플릿 미구현

`response_templates` 테이블 미사용. 현재는 순수 LLM 생성이라
기획의 "상담 템플릿 / 표준 문장" 요건이 빠져 있다.
`answer_drafts.template_id`·`is_adopted`·`edited_body` 컬럼도 채워지지 않는다
(초안 채택·수정 저장 기능 없음).

### 6-5. `audit_logs`가 비어 있다

차단 민원 증거 열람을 admin·mdt로 제한하긴 했으나 **누가 언제 열람했는지 기록하지 않는다.**
기획 문서상 민감정보 접근 추적은 필수 항목이다.

### 6-6. Alembic 미도입

스키마 변경 수단이 컨테이너 재생성뿐이다. 팀원이 각자 DB를 쓰기 시작하면 곧 어긋난다.
운영 전환 전 필수.

### 6-7. 기타

- 프론트 번들 726KB (Recharts 포함) — 코드 스플리팅 미적용
- 접수 응답이 AI 호출(F1·F2)을 동기로 기다림 — Claude 붙이면 응답 지연 체감
- `teacher_profiles` 근무시간 외 알림 차단 로직 미구현, `notifications` 미사용
- `MIN_SIMILARITY = 0.2` 임계값은 **해싱 임베딩 기준으로만 관찰**됨.
  실제 임베딩 API 도입 시 재조정 필요

### ORM 커버리지

스키마 23개 테이블 중 **14개**에 모델이 있다.

| 구분 | 테이블 |
|------|--------|
| ✅ 모델 있음 | `schools` `users` `students` `teacher_assignments` `complaints` `answer_drafts` `classifications` `risk_analyses` `content_filter_logs` `complaint_cases` `case_embeddings` `escalations` `recordings` `transcripts` |
| ❌ 모델 없음 | `teacher_profiles` `guardianships` `complaint_messages` `response_templates` `safe_numbers` `consultation_reservations` `call_sessions` `notifications` `audit_logs` |

---

## 7. 다음 우선순위

| 순위 | 작업 | 왜 |
|------|------|-----|
| 1 | **테스트 도입** (F3 필터 회귀 우선) | 지금 없는 것 중 가장 비싼 빚. 오차단은 사고 |
| 2 | **챗봇 자동 응대 실체화** + `complaint_messages` | 기획과 구현의 어긋남을 메움 |
| 3 | **학부모 동선** (`parent_id` 연결, 본인 민원 조회) | 로그인해도 갈 곳이 없는 상태 해소 |
| 4 | **`audit_logs` 기록** | 법적 요건에 가까움 |
| 5 | **Alembic 도입** | 팀 협업 본격화 전 |
| 6 | 실제 API 키로 F1·F2·F4·F5 품질 검증 | `MIN_SIMILARITY` 재조정 포함 |
| 7 | F4 템플릿, 초안 채택·수정 저장 | 기획 요건 잔여분 |
| 8 | F6 안심번호 (사업자 조사·계약) | 코드로 끝나지 않는 항목 |

---

## 8. 키 없이 동작하는 구조

로컬·데모에서 키 없이 앱이 뜨도록 모든 AI 경로에 fallback을 뒀다.

| 기능 | 키 있을 때 | 키 없을 때 |
|------|-----------|-----------|
| F1 분류 | Claude (`AI_CLASSIFY_MODEL`) | 키워드 규칙 (`keyword-fallback`) |
| F2 위험 | Claude | 키워드 휴리스틱 (`rule-risk-v1`) |
| F3 필터 | — | 결정론적 정규식 (`rule-filter-v1`) — 키 무관, 항상 동일 |
| F4 초안 | Claude (`AI_DRAFT_MODEL`) | 고정 템플릿 (`template-fallback`) |
| F5 임베딩 | OpenAI 호환 API (`EMBEDDING_API_KEY`) | 문자 n-gram 해싱 (`hash-embed-v1`) |
| F7 STT | CLOVA Speech | **fallback 없음 — 실패** (증빙 경로라 의도된 설계) |

F5는 두 방식의 벡터 공간이 다르므로 `case_embeddings.model_name`을 남기고
**검색 시 같은 모델의 벡터만 비교**한다. 임베딩 제공자를 바꾸면
`reindex_missing_case_embeddings`로 재인덱싱해야 한다.
