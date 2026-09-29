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
| `teacher@demo.sotong` | 교사 (3학년 2반 김학생 담당 → 민원함에 라우팅 건 표시) |
| `parent@demo.sotong` | 학부모 |

회원가입(`POST /api/auth/signup`)으로 **교사** 계정을 새로 만들 수 있다. 가입만으로는
민원이 보이지 않는다 — 관리자가 **교사 배정** 화면(`/teachers`)에서 담당 학년·반을 맡겨야
그 반 민원이 라우팅된다. 가입 시 본인이 담당 반을 고르게 하지 않는 이유는, 공개 경로라
아무나 "3학년 2반 담임"을 주장해 그 반 민원을 읽을 수 있기 때문이다. 관리자 계정은
가입으로 만들 수 없다(차단 민원 증거까지 열람하는 역할이라서). 시드나 DB 에서 직접 만든다.

학부모 접수 화면은 학교 코드로 학교를 찾는다. 데모 학교 코드는 `DEMO001`,
데모 학생은 `김학생 3학년 2반`이다.

### 기존 DB 업데이트 (로컬 볼륨·Neon)

학교 코드 컬럼이 추가됐다. 이미 만들어진 DB 에는 마이그레이션을 한 번 적용하고
시드를 다시 돌린다(둘 다 여러 번 실행해도 안전).

```bash
psql "<postgres://... 연결 문자열>" -f ../db/migrations/20260929_school_code.sql   # Neon 은 SQL Editor 에 붙여 넣어도 된다
DATABASE_URL="<연결 문자열>" python seed.py                          # 데모 학교에 코드 DEMO001 부여
psql "<postgres://... 연결 문자열>" -f ../db/migrations/20260929_guest_lookup.sql   # 비회원 조회·답변 (위 파일 다음에)
```

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
| `POST /api/auth/signup` | **교사** 회원가입 → 토큰 발급 (관리자는 가입 불가) | 공개 |
| `POST /api/auth/login` | 로그인 → 토큰 발급 | 공개 |
| `GET /api/auth/me` | 내 정보 | 로그인 |
| `GET /api/schools/by-code/{code}` | 학교 코드로 학교 찾기 (공개 정보만, 분당 30회) | 공개 |
| `POST /api/complaints` | 학부모 민원 접수 (F3→F1→F2→게이트→라우팅). 없는 학교·학생은 404 | 공개 (로그인 시 본인 귀속) |
| `PATCH /api/complaints/{id}/assignee` | 민원 담당 교사 지정·변경 | admin |
| `POST /api/complaints/{id}/messages` | 학부모에게 답변 보내기 (상태 → 답변 완료, 여러 번 가능) | teacher(본인 배정)·admin·mdt |
| `POST /api/complaints/lookup` | 비회원 민원 조회 — 접수번호 + 숫자 4자리 비밀번호. 10회 틀리면 10분 잠금 | 공개 |
| `GET /api/admin/teachers` | 이 학교 교사 + 미소속(갓 가입) 교사와 담당 반 | admin |
| `POST /api/admin/assignments` | 교사에게 학년·반 배정 (기존 담당 해제, 진행 중 민원 이동 선택) | admin |
| `DELETE /api/admin/assignments/{id}` | 배정 해제 | admin |
| `GET /api/complaints/mine` | 학부모 본인 민원함 | parent |
| `GET /api/complaints` | 민원 목록 (교사=본인 배정·필터 통과분 / admin·mdt=차단 건 포함 전체) | teacher·admin·mdt |
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
  목록·상세가 `deps.can_view_filtered()` 라는 **같은 규칙**을 쓴다 — 한쪽만 허용하면
  관리자가 증거에 도달할 화면이 없어진다(실제로 그랬다).
- 교사는 **본인에게 배정된 민원만** 상세·초안·이관 요청 가능.
- 학부모는 교사 민원함·상세엔 접근할 수 없고, `GET /api/complaints/mine` 으로
  **본인 민원만** 조회한다.
- **차단 민원(증거) 열람은 `audit_logs` 에 기록된다** — 아래 참고.

> ⚠️ **접수자 귀속은 토큰에서만 결정한다**(`deps.resolve_parent_id`).
> 접수 경로는 인증이 없으므로(학부모에게 로그인을 강제하지 않는 설계) 요청 본문의
> `parentId` 를 신뢰하면 **제3자가 임의의 학부모 명의로 민원을 넣을 수 있다.**
> 그래서 `ComplaintCreate` 에는 `parent_id` 필드가 아예 없다. 비로그인 접수는
> 익명(`parent_id=None`)으로 남는다.

## 감사 로그 (`services/audit.py`)

차단된 민원(F3 증거)의 원문에는 욕설·위협과 학생·학부모 민감정보가 담긴다.
**누가 언제 열람했는지** 기록하는 것은 기획 문서가 필수로 꼽은 요건이다.

기록은 `load_visible_complaint()` 한 곳에서 남긴다 — 상세·유사사례·초안 경로의
공통 관문이므로 여기 걸면 증거를 읽는 모든 경로가 덮인다. 목록 조회도 미리보기에
원문이 실려 나가므로 기록하되, 요청당 1줄 + 건수로 남겨 잡음을 줄인다.

| action | 시점 |
|--------|------|
| `VIEW_BLOCKED_COMPLAINT` | 차단 민원 상세·유사사례·초안 조회 (건별) |
| `LIST_BLOCKED_COMPLAINTS` | 목록에 차단 민원이 실려 나감 (요청당 1줄) |

- 권한 검사를 통과한 **실제 열람만** 기록한다. 403 으로 막힌 시도는 열람이 아니다.
- 차단되지 않은 일반 민원 조회는 기록하지 않는다. 남기면 로그가 잡음으로 가득 차
  증거 추적이 묻힌다.
- `ip_address` 는 `INET` 컬럼이라 IP 형식이 아니면 INSERT 가 실패한다. 그런데 실패는
  아래 fail-open 으로 삼켜지므로 **감사 로그가 조용히 사라진다** — 실제로 그랬다.
  그래서 형식을 확인해 유효하지 않으면 컬럼은 비우고 원본을 `detail.source` 에 남긴다.

> ⚠️ **기록 실패는 열람을 막지 않는다(fail-open).** 감사 로그 저장 문제로 관리자가
> 증거에 접근하지 못하면 정작 대응해야 할 사안 처리가 멈춘다. 다만 이건 정책
> 판단이다 — "감사 기록이 없으면 열람도 불가"를 요구하는 규정도 있으므로 운영
> 전환 시 법률 검토가 필요하다. 바꾸려면 `services/audit.py` 에서 예외를 올리면 된다.

## 유량 제한 (`core/rate_limit.py`)

`POST /api/complaints` 는 인증이 없다(학부모에게 로그인을 강제하지 않는 설계).
따라서 스크립트로 대량 제출하면 DB 가 차고 교사 민원함이 마비되므로, **유량 제한이
이 경로의 유일한 방어선**이다. 조회·로그인 등 다른 경로엔 걸리지 않는다.

| 항목 | 기본값 | 조정 |
|------|--------|------|
| 분당 | 5회 | `RATE_LIMIT_INTAKE_PER_MINUTE` |
| 시간당 | 100회 | `RATE_LIMIT_INTAKE_PER_HOUR` |

초과 시 `429` + `Retry-After` 헤더. 카운터는 Redis 를 우선 쓰고(여러 워커·인스턴스가
공유), 못 붙으면 프로세스 내 카운터로 떨어진다.

이 도메인에 맞춘 판단 세 가지:

- **Redis 가 죽으면 통과시킨다(fail-open).** 막으면 Redis 장애가 곧 '모든 민원 접수
  중단'이 되어 학교폭력 신고까지 못 들어온다. 가장 비싼 실패는 정당한 민원이
  사라지는 것이므로(F3 오차단 수정·자동응대 게이트와 같은 기준) 제한이 꺼지는
  쪽을 택하고 경고를 남긴다.
- **시간당 한도를 넉넉하게.** 익명 접수는 IP 로 세는데 같은 학교 와이파이·통신사
  NAT 뒤의 학부모들이 IP 를 공유한다. 사건이 터져 여러 학부모가 동시에 접수할 때
  정당한 민원이 서로를 막으면 안 된다. **로그인한 학부모는 사용자 id 로 세므로**
  이 문제가 없다.
- **`X-Forwarded-For` 는 기본적으로 믿지 않는다.** 프록시가 없는데 신뢰하면 공격자가
  헤더를 위조해 매 요청 다른 키를 만들어 한도를 무한히 우회한다. 프록시 뒤에
  배포할 때만 `TRUST_PROXY_HEADERS=true`.

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

두 층으로 나뉜다.

```bash
cd backend
pytest                 # 전부 (DB 없으면 라우트 테스트는 이유를 밝히고 skip)
pytest -m "not api"    # 단위만 — DB·네트워크 불필요, 1초 미만
pytest -m api          # 라우트만 — 실제 PostgreSQL 필요
```

**단위 185건** — 정책·규칙을 순수 함수로 검증. DB 없이 돈다.

| 파일 | 건수 | 대상 |
|------|------|------|
| `tests/test_content_filter.py` | 72 | F3 욕설·위협 필터 |
| `tests/test_synthetic_gen.py` | 32 | 합성 데이터 생성기 |
| `tests/test_gate.py` | 30 | 자동 응대 게이트 |
| `tests/test_eval_classifier.py` | 15 | 평가 하네스 지표 계산 |
| `tests/test_parent_mine.py` | 10 | `/mine` 라우트 등록·순서·역할 배선 |
| `tests/test_rate_limit.py` | 10 | 접수 유량 제한 정책 |
| `tests/test_parent_flow.py` | 9 | 민원 접수자 귀속 정책 |
| `tests/test_visibility.py` | 7 | 차단 민원(증거) 열람 권한 |

**라우트 61건** (`tests/test_api_routes.py` 50 + `tests/test_audit_log.py` 11) — TestClient 로 실제 요청을 보내
권한·귀속·파이프라인 결과를 검증한다. 정책 함수와 라우트 배선만 봐서는
"요청을 보냈을 때 실제로 403 이 나는가", "DB 에 무엇이 저장되는가"를 알 수 없다.
**접수자 귀속 사칭 버그가 정확히 그 틈으로 새어나갔다** — 정책은 있었지만
라우트에 연결되지 않은 상태였다.

SQLite 를 쓰지 않는 이유: 스키마가 네이티브 ENUM·`JSONB`·pgvector `VECTOR(1536)`
에 의존해서, 대체하면 프로덕션과 다른 것을 검증하게 된다.

```bash
docker run -d --name sotong-test-db -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=sotonghaeyo_test -p 5433:5432 pgvector/pgvector:pg16

TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/sotonghaeyo_test pytest
```

`TEST_DATABASE_URL` 이 없으면 `DATABASE_URL` 의 DB 이름 뒤에 `_test` 를 붙여 쓴다.
매 테스트마다 테이블을 비우므로 **DB 이름이 `_test` 로 끝나지 않으면 실행을 거부**한다.

CI(`.github/workflows/ci.yml`)가 PR·push 마다 둘 다 실행한다. pgvector 서비스
컨테이너를 붙였고, 연결이 안 되면 **라우트 테스트가 조용히 skip 되지 않도록**
별도 스텝에서 먼저 실패시킨다.

**F3 패턴을 넓히기 전에 `tests/test_content_filter.py` 를 먼저 읽을 것.**
폭력을 *신고하는* 민원은 가해 표현과 어휘가 겹쳐서("친구가 아이를 때려서 다쳤습니다"),
어휘 하나만 보고 차단하면 학교폭력 신고가 교사에게 가지 못하고 사라진다.
그래서 통과(오차단 방지) 케이스를 차단 케이스보다 촘촘히 고정해 두었다.

API 라우트·워커 테스트는 아직 없다.
(전체 현황은 [`docs/development-status.md`](../docs/development-status.md) 참고)

## 합성 민원 데이터 생성 (F1 학습·평가용)

학교 민원 분류는 이 프로젝트 고유 과제라 공개 라벨 데이터가 없다. 로컬 LLM 으로
카테고리별 민원을 생성해 초기 라벨 데이터를 만든다. 표준 라이브러리만 쓰므로
백엔드 venv 없이도 돌아간다.

```bash
ollama serve                                    # 별도 터미널
python scripts/gen_synthetic_complaints.py --count 30 --model gemma3:4b

# 평가셋 분리 + F3 오차단 측정까지
python scripts/gen_synthetic_complaints.py --count 30 --eval-ratio 0.2 --check-filter
```

주요 옵션: `--model` `--base-url`(OpenAI 호환) `--batch` `--categories` `--eval-ratio`.
출력은 `data/`(gitignore) 아래 JSONL. 분할은 본문 해시 기반이라 재실행해도
같은 문장이 같은 쪽(train/eval)에 간다.

**설계상 주의 — 프롬프트에서 라벨이 오기 때문에 모델이 주제를 벗어나면 오라벨이 된다.**
실제로 gemma3:4b 가 `violence_dispute` 프롬프트에 "학습 부진 상담"을 만든 적이 있다.
그래서 생성 후 카테고리별 필수 신호를 검사해 주제 이탈을 버리고, 프롬프트 지시문이
본문에 새어 들어온 것도 거른다(둘 다 실제로 발생했던 오염이다).

`--check-filter` 는 생성된 **정당한** 민원이 F3 에 차단되는지 측정한다. 합성 데이터는
정의상 전부 정당하므로 차단되면 그게 곧 오차단이고, F3 패턴을 고칠 때 회귀 지표가 된다.

> ⚠️ 합성 데이터는 실제 민원과 분포가 다르다(더 정제되고 오타·비문이 적다).
> 모든 레코드에 `source="synthetic"` 이 박히며, **학습 전 표본 검수는 필수**다.
> 실제 민원이 쌓이는 대로 재학습·재평가해야 한다.

## F1 분류기 평가 (scripts/eval_classifier.py)

**정확도만 보면 안 된다.** 전체 정확도 95%인 분류기가 학교폭력 민원만 골라서 틀리면
최악이고, 80%여도 위험한 민원을 놓치지 않으면 훨씬 낫다. 그래서 세 층으로 보고한다.

| 층 | 내용 |
|----|------|
| 1. 일반 지표 | 카테고리별 정밀도·재현율·F1, macro F1, 혼동행렬 |
| 2. **치명 오류** | 학교폭력·분쟁을 `administrative` 로 예측한 비율 — 이 경로만이 자동 응대로 이어진다 |
| 3. **최종 안전** | 분류기 + 자동응대 게이트를 통과시켜, 실제로 자동 응대될 위험 민원 건수 |

2번이 0이 아니어도 3번이 0이면 게이트가 막아준 것이다. **3번이 0이 아니면 배포하면
안 된다.** `--max-unsafe` 로 임계값을 넘으면 종료코드 1을 돌려주므로 CI 에 걸 수 있다.

```bash
# 규칙 기반 fallback 기준선 — 모델을 만들기 전에 이 숫자를 기록해 둘 것
python scripts/eval_classifier.py --data data/synthetic_complaints.jsonl

# 실제 LLM 수준의 신뢰도를 가정해 게이트 방어력만 보기
python scripts/eval_classifier.py --data ... --confidence 0.95

# CI 용 — 위험 민원 자동응대가 1건이라도 있으면 실패
python scripts/eval_classifier.py --data ... --max-unsafe 0
```

새 모델(파인튜닝 등)을 만들면 `classify()` 구현만 갈아끼우고 같은 명령으로 비교한다.
기준선을 못 넘으면 만든 의미가 없다.

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
- [x] ~~AI 서비스 단위 테스트 (필터 오차단 회귀 방지)~~ — 단위 175 + 라우트 46 = 221건, `pytest` (CI 에서 자동 실행)
- [x] ~~자동 응대 게이트: 신뢰도·위험도·안전 키워드 교차 검증~~
- [x] ~~F1 학습·평가 기반: 합성 데이터 생성기 + 평가 하네스 + 기준선~~
- [ ] **API 라우트·워커 테스트** (`TestClient` + 테스트 DB) — 안전 판정 경로는
      덮였으나 라우트·권한·워커는 아직 일회성 스크립트로만 검증
- [ ] Alembic 마이그레이션 도입 (`alembic init`) — 운영 전환 전 필수
- [x] ~~`audit_logs` 기록: 차단 민원 증거 열람 추적~~
- [ ] 챗봇 자동 응대 실체화 (`complaint_messages`) — 지금은 `auto_answered` 상태만
      기록되고 실제 응대 문구가 남지 않는다
- [ ] 학부모 동선: 접수 시 `parent_id` 연결 + 본인 민원 조회
- [ ] F6 안심번호·예약 상담 (통신사/제3자 가상번호 연동)
- [ ] `violence_dispute` 평가 표본 확대 후 기준선 재측정 (현재 3건, 재현율 0.333)
