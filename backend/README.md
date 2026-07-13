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
python seed.py    # 데모 학교·학생·교사배정 + 계정 3개 (비번 demo1234)
```

- API 문서(Swagger): http://localhost:8000/docs
- 헬스체크: http://localhost:8000/health

> `ANTHROPIC_API_KEY`를 비워두면 AI 서비스가 **규칙 기반 fallback**으로 동작해
> 키 없이도 앱이 뜹니다(F1 키워드 분류 / F2 휴리스틱 위험 / F4 템플릿 답변).
> F3 욕설 필터는 애초에 결정론적 규칙 기반이라 키와 무관하게 동일 동작.

## 데모 계정 (seed.py, 비밀번호 `demo1234`)

| 이메일 | 역할 |
|--------|------|
| `admin@demo.sotong` | 관리자 |
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
│  └─ _enums.py       #   PostgreSQL 네이티브 ENUM 바인딩 (schema.sql의 CREATE TYPE와 매핑)
├─ schemas/           # Pydantic 입출력 스키마
│  └─ base.py         #   CamelModel — JSON은 camelCase, 내부는 snake_case (shared 계약 정합)
├─ api/
│  ├─ deps.py         # get_current_user 등 의존성
│  └─ routes/         # auth(signup/login/me) · complaints(F1~F4) · dashboard(F9)
├─ services/ai/       # classifier(F1) · risk(F2) · content_filter(F3) · drafter(F4)
│  ├─ routing.py      #   teacher_assignments 기반 담당 교사 자동 배정
│  └─ client.py       #   Anthropic 래퍼 (키 없으면 None → fallback)
└─ seed.py            # 데모 시드 스크립트 (backend/ 루트)
```

> **인증/암호화 주의:** `passlib` 대신 `bcrypt`를 직접 사용한다. passlib 1.7.4가
> 최신 bcrypt와 호환성 버그가 있어서다(`requirements.txt` 참고).

## API 개요

| 메서드·경로 | 설명 | 인증 |
|-------------|------|------|
| `POST /api/auth/signup` | 교사·관리자 회원가입 → 토큰 발급 | - |
| `POST /api/auth/login` | 로그인 → 토큰 발급 | - |
| `GET /api/auth/me` | 내 정보 | ✅ |
| `POST /api/complaints` | 학부모 민원 접수 (F3→F1→F2→라우팅) | - |
| `GET /api/complaints` | 교사 민원함 (필터 통과분, 교사면 본인 배정) | ✅ |
| `GET /api/complaints/{id}` | 민원 상세 (차단 건은 admin·mdt만) | ✅ |
| `POST /api/complaints/{id}/draft` | F4 답변 초안 생성 | ✅ |
| `GET /api/dashboard/stats` | F9 집계 | ✅ |

## 접수 파이프라인 (F1~F3 + 라우팅)

`routes/complaints.create_complaint` 가 게이트웨이 파이프라인을 태운다:

```
F3 욕설·위협 필터 → F1 분류 → F2 위험 → 상태 결정 + 라우팅 + 이력 영속화
```

| 결과 | status | 처리 |
|------|--------|------|
| 욕설·위협 감지 | `filtered_blocked` | 교사 미노출, 원문을 `content_filter_logs.raw_evidence` 로 증거 보관 |
| 단순 행정 | `auto_answered` | 챗봇 자동 응대 후보 |
| 그 외 정당한 민원 | `pending_teacher` | `teacher_assignments` 기반 담당 교사 자동 배정 |

- **F3**(`services/ai/content_filter.py`)는 증거·법적 대응을 위해 **결정론적 규칙 기반**(정규식). LLM 확률 판단에 맡기지 않음.
- **F2**(`services/ai/risk.py`)는 Claude + 키워드 휴리스틱 fallback.
- 분류·위험 결과는 `classifications` / `risk_analyses` 이력 테이블에 남고, `GET /api/complaints/{id}`(admin·mdt만 차단 건 열람) 로 조회.

## DB

`../db/schema.sql`을 PostgreSQL 15+(pgvector)에 적용(위 Docker 절차 참고). ORM 모델은
`user`/`complaint`/`analysis` 테이블을 커버하며, 나머지는 스키마를 참조해 같은 패턴으로
추가한다. ENUM 컬럼은 `models/_enums.py`로 네이티브 타입에 바인딩된다.
운영 전환 시 **Alembic** 도입 권장(`alembic init`).

## 다음 채울 곳 (TODO)

- [x] ~~F2 위험 탐지 · F3 욕설 필터를 접수 파이프라인에 연결~~
- [x] ~~민원 라우팅: `teacher_assignments` 기반 `assigned_teacher_id` 자동 배정~~
- [x] ~~사용자 시드(`python seed.py`) / 회원가입(`POST /api/auth/signup`)~~
- [ ] F5 RAG: `complaint_cases` + pgvector 임베딩 검색 → drafter에 주입
- [ ] 역할별 권한 세분화 (라우트 가드)
- [ ] F8 이관(escalations): 교사 → MDT/관리자 이관 엔드포인트
- [ ] Celery + Redis 워커 (STT 변환·배치 분석)
