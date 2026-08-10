# 소통해요 Backend (FastAPI)

## 실행 (전체 순서)

### 0) 사전 준비
- **Python 3.11 또는 3.12 권장.** (3.13/3.14에서는 `requirements.txt`의 핀 버전이
  아직 휠을 제공하지 않아 빌드가 실패할 수 있음 → 최신 버전으로 대체 설치 필요)
- **Docker Desktop** — DB(PostgreSQL + pgvector)를 컨테이너로 띄운다. Postgres를
  직접 설치할 필요 없음.

### 1) DB 컨테이너 (Docker)
```bash
# Postgres 16 + pgvector 컨테이너 실행
docker run -d --name sotong-db \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=sotonghaeyo \
  -p 5432:5432 pgvector/pgvector:pg16

# 스키마 적용 — 파일을 컨테이너로 복사 후 psql이 직접 읽게 한다.
docker cp ../db/schema.sql sotong-db:/tmp/schema.sql
docker exec sotong-db psql -U postgres -d sotonghaeyo -f /tmp/schema.sql
```
> ⚠️ **PowerShell에서 `Get-Content schema.sql | docker exec ... psql` 방식은 쓰지 말 것.**
> UTF-8 한글 주석이 파이프에서 깨져 일부 컬럼이 유실된다. 위처럼 `docker cp` +
> `psql -f`로 넣어야 안전하다.

### 2) 백엔드 서버
```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# bash:              source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # 기본값이면 위 Docker DB에 그대로 연결됨
uvicorn app.main:app --reload --port 8000
```

### 3) 데모 데이터 시드
```bash
python seed.py    # 데모 학교·학생·교사배정 + 계정 4개(비번 demo1234) + F5 사례 4건
```

### 4) Celery 워커 (선택 — F5 인덱싱·F7 STT 비동기 처리)
```bash
# Redis 컨테이너
docker run -d --name sotong-redis -p 6379:6379 redis:7

celery -A app.worker.celery_app:celery_app worker --loglevel=info
celery -A app.worker.celery_app:celery_app beat   --loglevel=info   # 주기 작업
```
> API 서버만 띄워도 모든 기능이 동작한다. 워커는 사례 임베딩 재인덱싱과
> 녹음 STT 변환을 요청 경로 밖으로 빼기 위한 것이다.

- API 문서(Swagger): http://localhost:8000/docs
- 헬스체크: http://localhost:8000/health

> `ANTHROPIC_API_KEY`를 비워두면 AI 서비스가 **규칙 기반 fallback**으로 동작해
> 키 없이도 앱이 뜹니다(F1 키워드 분류 / F2 휴리스틱 위험 / F4 템플릿 답변).
> F3 욕설 필터는 애초에 결정론적 규칙 기반이라 키와 무관하게 동일 동작.
> F5 임베딩도 `EMBEDDING_API_KEY`가 없으면 결정론적 해싱 임베딩으로 동작한다.

## 데모 계정 (seed.py, 비밀번호 `demo1234`)

| 이메일 | 역할 |
|--------|------|
| `admin@demo.sotong` | 관리자 |
| `mdt@demo.sotong` | 민원대응팀(MDT) |
| `teacher@demo.sotong` | 교사 (시드 학생 배정 있음 → 민원함에 라우팅 건 표시) |
| `parent@demo.sotong` | 학부모 |

회원가입(`POST /api/auth/signup`)으로 교사·관리자 계정을 새로 만들 수도 있다.

## 구조

```
app/
├─ main.py            # FastAPI 엔트리 + CORS
├─ core/              # config(env), security(JWT + bcrypt 직접 사용)
├─ db/session.py      # SQLAlchemy 엔진·세션·Base
├─ models/            # ORM 모델
│  ├─ user.py         #   School · User · Student
│  ├─ complaint.py    #   Complaint · AnswerDraft
│  ├─ analysis.py     #   Classification · RiskAnalysis · ContentFilterLog · TeacherAssignment
│  ├─ case.py         #   ComplaintCase · CaseEmbedding (F5, pgvector)
│  ├─ escalation.py   #   Escalation (F8)
│  ├─ recording.py    #   Recording · Transcript (F7)
│  └─ _enums.py       #   PostgreSQL 네이티브 ENUM 바인딩 (schema.sql의 CREATE TYPE와 매핑)
├─ schemas/           # Pydantic 입출력 스키마
│  └─ base.py         #   CamelModel — JSON은 camelCase, 내부는 snake_case (shared 계약 정합)
├─ api/
│  ├─ deps.py         # get_current_user · require_roles · load_visible_complaint
│  └─ routes/         # auth · complaints(F1~F5) · escalations(F8) · cases(F5) · dashboard(F9)
├─ services/
│  ├─ ai/             # classifier(F1) · risk(F2) · content_filter(F3) · drafter(F4)
│  │  ├─ embedding.py #   임베딩 생성 (외부 API → 해싱 fallback)
│  │  ├─ retriever.py #   F5 유사 사례 검색 (pgvector 코사인)
│  │  ├─ routing.py   #   teacher_assignments 기반 담당 교사 자동 배정
│  │  └─ client.py    #   Anthropic 래퍼 (키 없으면 None → fallback)
│  └─ stt.py          # F7 CLOVA Speech 변환
├─ worker/            # Celery 앱 + 태스크 (사례 인덱싱 · STT 변환)
└─ seed.py            # 데모 시드 스크립트 (backend/ 루트)
```

> **인증/암호화 주의:** `passlib` 대신 `bcrypt`를 직접 사용한다. passlib 1.7.4가
> 최신 bcrypt와 호환성 버그가 있어서다(`requirements.txt` 참고).

## API 개요

| 메서드·경로 | 설명 | 권한 |
|-------------|------|------|
| `POST /api/auth/signup` | 교사·관리자 회원가입 → 토큰 발급 | 공개 |
| `POST /api/auth/login` | 로그인 → 토큰 발급 | 공개 |
| `GET /api/auth/me` | 내 정보 | 로그인 |
| `POST /api/complaints` | 학부모 민원 접수 (F3→F1→F2→라우팅) | 공개 |
| `GET /api/complaints` | 교사 민원함 (필터 통과분, 교사면 본인 배정) | teacher·admin·mdt |
| `GET /api/complaints/{id}` | 민원 상세 | teacher(본인 배정)·admin·mdt |
| `GET /api/complaints/{id}/similar-cases` | F5 유사 사례 검색 | teacher·admin·mdt |
| `POST /api/complaints/{id}/draft` | F4 답변 초안 생성 (F5 사례 주입) | teacher·admin·mdt |
| `GET /api/complaints/{id}/drafts` | 초안 이력 | teacher·admin·mdt |
| `POST /api/escalations` | F8 이관 요청 | teacher·admin |
| `GET /api/escalations` | F8 이관 목록 (`?status=`) | admin·mdt |
| `PATCH /api/escalations/{id}` | F8 접수/해결/반송 | admin·mdt |
| `POST /api/cases` | F5 지식베이스 사례 등록(+임베딩) | admin·mdt |
| `GET /api/cases` | F5 사례 목록 | teacher·admin·mdt |
| `GET /api/dashboard/stats` | F9 집계 | admin·mdt |

### 권한 규칙

`api/deps.py` 의 `require_roles(...)` 로 라우트 단위 역할을 통제하고,
`load_visible_complaint(...)` 로 건별 열람 권한을 통제한다.

- 토큰의 `role` 클레임이 아니라 **DB 의 현재 역할**로 판정한다 (발급 후 역할 변경·정지 반영).
- 차단된 민원(`filtered=true`, 증거)은 **admin·mdt 만** 열람 가능.
- 교사는 **본인에게 배정된 민원만** 상세·초안·이관 요청 가능.
- 학부모는 접수만 하고 민원함·상세엔 접근하지 않는다.

## 접수 파이프라인 (F1~F3 + 라우팅)

`routes/complaints.create_complaint` 가 게이트웨이 파이프라인을 태운다:

```
F3 욕설·위협 필터 → F1 분류 → F2 위험 → 자동응대 게이트 → 라우팅 + 이력 영속화
```

| 결과 | status | 처리 |
|------|--------|------|
| 욕설·위협 감지 | `filtered_blocked` | 교사 미노출, 원문을 `content_filter_logs.raw_evidence` 로 증거 보관 |
| 단순 행정 + 게이트 통과 | `auto_answered` | 챗봇 자동 응대 후보 |
| 그 외 전부 (게이트 보류 포함) | `pending_teacher` | `teacher_assignments` 기반 담당 교사 자동 배정 |

- **F3**(`services/ai/content_filter.py`)는 증거·법적 대응을 위해 **결정론적 규칙 기반**(정규식). LLM 확률 판단에 맡기지 않음.
- **F2**(`services/ai/risk.py`)는 Claude + 키워드 휴리스틱 fallback.
- 분류·위험 결과는 `classifications` / `risk_analyses` 이력 테이블에 남고, `GET /api/complaints/{id}`(admin·mdt만 차단 건 열람) 로 조회.

### 자동 응대 게이트 (`services/ai/gate.py`)

'단순 행정'이라는 AI 판단만으로 자동 응대해도 되는지 한 번 더 검사한다.
오분류 비용이 비대칭이기 때문 — 학교폭력 민원이 단순 행정으로 오분류되면
자동 응대되고 **교사에게 영원히 가지 않는다.** 반대 방향 오류는 교사가 한 번 더 볼 뿐이다.

네 조건을 **모두** 통과해야 자동 응대한다:

1. 단순 행정으로 분류됨
2. 자동 응대 금지 신호 없음 — 학폭·자해·성 관련·학대 키워드 (결정론적 안전망)
3. 위험도가 `high`/`critical` 아님 (F2 교차 검증)
4. 분류 신뢰도 ≥ `AUTO_ANSWER_MIN_CONFIDENCE` (기본 0.7)

2번을 규칙 기반으로 둔 이유는 F3와 같다. 게다가 F2는 *공격성*을 보므로 차분하게
서술된 심각한 사안은 위험도가 낮게 나온다 — "아이가 자해를 해서 상담 서류를
신청하고 싶습니다"는 F1이 `administrative`, F2가 `low`로 보지만 2번이 막는다.

> ⚠️ **기본값에서는 fallback 분류기(신뢰도 0.4)로 자동 응대가 발생하지 않는다.**
> 키워드 매칭만으로 자동 응대하지 않겠다는 의도된 동작이다. 데모에서 자동 응대를
> 보여줘야 하면 `AUTO_ANSWER_MIN_CONFIDENCE=0.3` 으로 낮춘다.

보류된 건은 근거와 함께 로그에 남는다 (임계값 조정의 유일한 근거):

```
INFO app.api.routes.complaints | 자동 응대 보류 → 교사 배정: 분류 신뢰도 부족(0.40 < 0.70)
INFO app.api.routes.complaints | 자동 응대 보류 → 교사 배정: 자동 응대 금지 신호 감지: 자해
```

## 테스트

```bash
cd backend && pytest        # tests/ — DB·네트워크 없이 도는 순수 함수 테스트
```

| 파일 | 건수 | 대상 |
|------|------|------|
| `tests/test_gate.py` | 30 | 자동 응대 게이트 |
| `tests/test_content_filter.py` | 68 | F3 욕설·위협 필터 |

**F3 패턴을 넓히기 전에 `tests/test_content_filter.py` 를 먼저 읽을 것.**
폭력을 *신고하는* 민원은 가해 표현과 어휘가 겹쳐서("친구가 아이를 때려서 다쳤습니다"),
어휘 하나만 보고 차단하면 학교폭력 신고가 교사에게 가지 못하고 사라진다.
그래서 통과(오차단 방지) 케이스를 차단 케이스보다 촘촘히 고정해 두었다.

API 라우트·워커 테스트는 아직 없다.
(전체 현황은 [`docs/development-status.md`](../docs/development-status.md) 참고)

## 유사 사례 검색 (F5)

`complaint_cases` + `case_embeddings`(pgvector) 를 코사인 거리로 검색해 F4 초안
프롬프트에 근거로 주입한다.

- 임베딩은 OpenAI 호환 `/v1/embeddings` 를 HTTP로 직접 호출(SDK 의존성 없이).
  키가 없거나 호출이 실패하면 **결정론적 해싱 임베딩**(문자 2~3-gram signed hashing)으로 fallback.
- 두 방식의 벡터는 공간이 달라 섞으면 안 되므로, `case_embeddings.model_name` 을 남기고
  **검색 시 같은 모델의 벡터만 비교**한다.
- 유사도 `MIN_SIMILARITY`(0.2) 미만은 초안 프롬프트에 넣지 않는다 — 무관한 사례가
  섞이면 초안 품질이 오히려 떨어지기 때문.

## 이관 (F8)

교사가 단독 대응하기 어려운 민원을 관리자·MDT로 넘긴다. AI 오차단·오분류에 대한
사람 재검토 경로이기도 하다.

| 이관 처리 | escalations.status | complaints.status |
|-----------|--------------------|-------------------|
| 요청 | `requested` | `escalated` |
| 접수 | `accepted` | (유지) |
| 해결 | `resolved` | `closed` (+`closed_at`) |
| 반송 | `rejected` | `pending_teacher` |

같은 민원에 진행 중(`requested`/`accepted`)인 이관이 있으면 중복 요청은 409.

## 비동기 워커 (Celery)

`app/worker/tasks.py`

| 태스크 | 용도 |
|--------|------|
| `index_case_embedding(case_id)` | F5 단건 사례 임베딩 생성·갱신 |
| `reindex_missing_case_embeddings()` | 임베딩 누락분 배치 채움 (beat: 매일 04:00 KST) |
| `transcribe_recording(recording_id)` | F7 녹음 → 대화록 변환 |

> STT 는 증빙을 만드는 경로라 미설정 시 **조용히 넘기지 않고 실패**시킨다(빈 대화록이
> '아무 말도 없었다'로 오해되지 않도록). 녹음 고지·동의(`consent_given`)가 기록되지
> 않은 건도 변환을 거부한다(통신비밀보호법).

## DB

`../db/schema.sql`을 PostgreSQL 15+(pgvector)에 적용(위 Docker 절차 참고). ORM 모델은
`user`/`complaint`/`analysis` 테이블을 커버하며, 나머지는 스키마를 참조해 같은 패턴으로
추가한다. ENUM 컬럼은 `models/_enums.py`로 네이티브 타입에 바인딩된다.
운영 전환 시 **Alembic** 도입 권장(`alembic init`).

## 다음 채울 곳 (TODO)

- [x] ~~F2 위험 탐지 · F3 욕설 필터를 접수 파이프라인에 연결~~
- [x] ~~민원 라우팅: `teacher_assignments` 기반 `assigned_teacher_id` 자동 배정~~
- [x] ~~사용자 시드(`python seed.py`) / 회원가입(`POST /api/auth/signup`)~~
- [x] ~~F5 RAG: `complaint_cases` + pgvector 임베딩 검색 → drafter에 주입~~
- [x] ~~역할별 권한 세분화 (라우트 가드)~~
- [x] ~~F8 이관(escalations): 교사 → MDT/관리자 이관 엔드포인트~~
- [x] ~~Celery + Redis 워커 (STT 변환·배치 분석)~~
- [ ] Alembic 마이그레이션 도입 (`alembic init`) — 운영 전환 전 필수
- [ ] F6 안심번호·예약 상담 (통신사/제3자 가상번호 연동)
- [ ] `audit_logs` 기록: 증거·녹음 열람 추적
- [ ] AI 서비스 단위 테스트 (필터 오차단 회귀 방지)
