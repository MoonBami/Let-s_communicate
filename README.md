<div align="center">

# 🗣️ 소통해요 (Sotonghaeyo)

**교사 민원 보조 AI 시스템**

학부모 민원이 교사에게 직접 가지 않고 **AI 플랫폼을 한 번 거쳐**,
정당한 민원만 걸러서 전달하는 게이트웨이형 서비스.

`React + Vite` · `FastAPI` · `PostgreSQL + pgvector` · `Claude API`

</div>

---

## 📌 왜 만드나

최근 교권 침해·악성 민원이 사회적 이슈로 떠오르며 교사의 업무 피로도가 매우 높습니다.
「소통해요」는 다음 문제를 완화합니다.

- 반복 민원과 감정 소모로 인한 **교사 업무 피로**
- 민원 기록 관리·공식 답변 작성에 드는 **과도한 행정 시간**
- 교사 실번호 노출로 인한 **사생활 침해·시간 외 연락 부담**
- 악성·위협성 민원에 대한 **증거 확보·대응 체계 부재**

> **핵심 아이디어:** 학부모 민원 → `[AI 필터·분류]` → **정당한 민원만 교사에게**.
> 단순 행정은 챗봇이 자동 응대, 욕설·위협은 차단하고 증거로 기록.

기획·의사결정 배경 전문은 [`docs/project-overview.md`](docs/project-overview.md) 참고.

---

## ✨ 기능 (F1~F9)

| ID | 기능 | 설명 | 단계 |
|----|------|------|------|
| **F1** | 민원 자동 분류 & 라우팅 | 단순 행정 / 학습·생활·성적 / 학교폭력·분쟁 자동 분류 | ✅ 완료 |
| **F4** | 공식 답변 초안 & 템플릿 | 정중한 답변 초안 자동 생성 + 표준 문장 | ✅ 완료 |
| **F9** | 관리자 통계 대시보드 | 유형·건수·위험도·대응 현황 시각화 | ✅ 완료 |
| **F2** | 감정·위험 탐지 | 감정/공격성 분석 → 위험 민원 우선순위 | ✅ 완료 |
| **F3** | 욕설·위협 필터 & 증거 | 욕설·협박 차단(교사 미노출), 원문 증빙 보관 | ✅ 완료 |
| **F5** | 유사 사례 검색(RAG) | 과거 사례 의미 기반 검색·대응 추천 | ✅ 완료 |
| **F8** | MDT 이관 | 버튼 하나로 관리자·민원대응팀 이관 | ✅ 완료 |
| **F7** | 실시간 녹음·STT | 통화·상담 녹음 → 대화록 자동 변환(증빙) | 🟡 변환 파이프라인만 |
| **F6** | 안심번호·예약 상담 | 실번호 비노출 통화·채팅, 근무시간 외 차단 | 🔵 3차 (외부 사업자 연동 필요) |

---

## 🏗️ 아키텍처

게이트웨이 구조 — 접수 → AI 처리 → 교사 → 관리.

```
                  ┌─────────────────────────────────────────┐
학부모 민원 입력 ─▶│  AI 처리 계층                              │
 (웹/안심번호)     │  F1 분류 → F2 위험 → F3 욕설필터           │
                  └───────────────┬──────────────┬───────────┘
                                  │              │
                       단순 행정  │              │  위협성
                  ┌───────────────▼──┐        ┌──▼──────────────┐
                  │ 챗봇 자동 응대     │        │ 차단 + 증거 기록 │
                  └──────────────────┘        └─────────────────┘
                                  │
                        정당한 민원만
                  ┌───────────────▼───────────────┐
                  │  교사 계층                      │
                  │  민원함 · F4 답변초안 · F5 사례   │
                  └───────────────┬────────────────┘
                                  │
                  ┌───────────────▼───────────────┐
                  │  관리 계층                      │
                  │  F8 이관 · F7 증빙 · F9 대시보드 │
                  └────────────────────────────────┘
```

---

## 📂 프로젝트 구조 (모노레포)

```
Let's_communicate/
├─ apps/
│  └─ web/            # 반응형 웹 (Vite + React + TS) — 교사·학부모·관리자 공용
│     └─ (추후 apps/mobile → Expo/RN, 백엔드 API·shared 타입 재사용)
├─ packages/
│  └─ shared/         # 웹·앱 공용 타입 / ENUM / API 경로 (단일 소스)
├─ backend/           # FastAPI + SQLAlchemy + AI 서비스
│  ├─ app/services/ai # F1 분류 · F2 위험 · F3 욕설필터 · F4 답변초안 · F5 임베딩/검색
│  ├─ app/worker/     # Celery 태스크 (사례 인덱싱 · F7 STT 변환)
│  └─ seed.py         # 데모 계정·데이터·F5 사례 시드
├─ db/
│  └─ schema.sql      # PostgreSQL 15+ / pgvector 스키마
└─ docs/              # 기획·정리 문서
```

**왜 이 구조?** 백엔드를 Python(FastAPI)로 두면(=AI 생태계) 웹은 순수 SPA(Vite)가 가볍고,
`packages/shared`에 타입/API 계약을 모아두면 **나중에 만들 모바일 앱(RN)이 웹과 그대로 공유**합니다.
(Next.js의 SSR·서버 기능은 웹 전용이라 앱에서 재사용이 안 돼 이 프로젝트엔 이점이 상쇄됨)

---

## 🛠️ 기술 스택

| 영역 | 선택 |
|------|------|
| **프론트** | React 18 · TypeScript · Vite · Tailwind · TanStack Query · Zustand · React Router · React Hook Form + Zod · Recharts |
| **백엔드** | Python · FastAPI · SQLAlchemy 2 · Pydantic v2 · JWT(python-jose) · Celery + Redis · pytest |
| **DB / 인프라** | PostgreSQL 15+ · pgvector · Redis · S3 호환 스토리지 · Docker |
| **AI** | Claude API (분류·답변) · 임베딩 RAG(pgvector) · STT(CLOVA/Whisper) |

---

## 🚀 시작하기

### 사전 준비
- **Node.js 20+**
- **Python 3.11 또는 3.12** (3.13/3.14는 핀 버전 휠 미제공으로 빌드 실패 가능 → 최신 버전 대체 설치 필요)
- **Docker Desktop** — DB를 컨테이너로 띄운다. PostgreSQL을 직접 설치하지 않아도 됨.

### 0) 더 빠른 방법: Docker Compose 한 번에

아래 1~5 단계(DB·백엔드·프론트·워커를 각각 손으로 띄우는 것)를 컨테이너
하나로 대신할 수 있다. 팀원 간 환경 차이를 없애고 싶을 때 이 방법을 권장.

```bash
cp backend/.env.example backend/.env    # 기본값 그대로면 아래 서비스에 바로 연결됨
docker compose up --build               # db·redis·backend·worker·beat·web 전부 기동
docker compose exec backend python seed.py   # 데모 계정·데이터 시드 (최초 1회)
```
- DB 스키마(`db/schema.sql`)는 `db` 컨테이너 최초 생성 시 자동 적용됨(볼륨이 비어있을 때만).
  스키마를 고쳤는데 반영이 안 되면 `docker compose down -v`로 볼륨을 지우고 다시 `up`.
- 코드는 볼륨 마운트되어 있어 backend는 `--reload`, web은 Vite dev server로 핫리로드된다.
- 특정 서비스만 띄우고 싶으면 `docker compose up -d db redis` 처럼 서비스명을 지정.
- 로그: `docker compose logs -f backend` (worker/beat/web도 동일)
- 종료: `docker compose down` (데이터까지 지우려면 `-v` 추가)

아래는 컨테이너 없이 직접 실행하는 수동 절차(디버깅이나 IDE 연동 시 유용).

### 1) 데이터베이스 (Docker)
```bash
# Postgres 16 + pgvector 컨테이너
docker run -d --name sotong-db \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=sotonghaeyo \
  -p 5432:5432 pgvector/pgvector:pg16

# 스키마 적용 (파일 복사 후 psql이 직접 읽게 — 파이프 인코딩 깨짐 방지)
docker cp db/schema.sql sotong-db:/tmp/schema.sql
docker exec sotong-db psql -U postgres -d sotonghaeyo -f /tmp/schema.sql
```
> ⚠️ PowerShell에서 `Get-Content ... | docker exec psql`는 UTF-8 한글 주석이 깨져
> 스키마가 일부 유실됩니다. 반드시 위처럼 `docker cp` + `psql -f`로 넣으세요.

### 2) 백엔드 (FastAPI)
```bash
cd backend
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# bash:              source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # 기본값이면 위 Docker DB에 그대로 연결됨
uvicorn app.main:app --reload --port 8000   # → http://localhost:8000/docs
python seed.py            # (별도 터미널) 데모 계정·데이터 시드
```
> `/api` 요청은 Vite가 8000번으로 프록시하므로 개발 중 CORS 설정이 필요 없습니다.
> `ANTHROPIC_API_KEY`가 없으면 AI가 **규칙 기반 fallback**으로 동작해 키 없이도 앱이 뜹니다.

### 3) 프론트엔드 (웹)
```bash
npm install            # 루트에서 (workspaces 전체 설치)
npm run dev:web        # → http://localhost:5173
```

### 4) 로그인 / 접속
- 웹: http://localhost:5173
- 데모 계정(비번 `demo1234`): `admin@demo.sotong` · `mdt@demo.sotong` · `teacher@demo.sotong` · `parent@demo.sotong`
- 로그인 화면에서 **회원가입**(교사·관리자) 또는 **학부모 민원 접수**(로그인 불필요)로 이동
- 운영 전환 시 스키마 마이그레이션은 **Alembic** 도입 권장

### 5) (선택) Celery 워커
사례 임베딩 재인덱싱·녹음 STT 변환을 요청 경로 밖에서 처리한다. API 서버만
띄워도 모든 기능은 동작하므로 필수는 아니다.
```bash
docker run -d --name sotong-redis -p 6379:6379 redis:7
cd backend && celery -A app.worker.celery_app:celery_app worker --loglevel=info
```

---

## 🗓️ 로드맵

| 단계 | 기간(약) | 범위 |
|------|---------|------|
| Phase 0 · 설계 | 2주 | 요구사항·법률 검토, DB/아키텍처, API 명세, 디자인 시안 |
| Phase 1 · MVP | 6~8주 | **F1 분류 · F4 답변초안 · F9 대시보드** (웹) |
| Phase 2 · AI 고도화 | 6~8주 | F2 위험 · F3 욕설필터 · F5 RAG · F8 이관 |
| Phase 3 · 확장 | 8주+ | F6 안심번호·통화 · F7 녹음 STT · (선택) 교사용 모바일 앱 |

---

## 👥 팀 구성

| 역할 | 담당 |
|------|------|
| AI/ML (1) | F1·F2·F3·F4·F5·F7 AI 로직, 프롬프트·RAG·가드레일 |
| 프론트엔드 (1) | 반응형 웹 전체 (민원함·접수·대시보드·채팅) |
| 백엔드 A (1) | 코어: API·인증·권한, DB, 라우팅/필터, F8 이관 |
| 백엔드 B (1) | 인프라: 배포·CI/CD, 큐, F6 안심번호·통화, AI 서빙 |

---

## ⚖️ 법적·보안·윤리 (필수 검토)

- **통화 녹음(F7):** 대화 당사자 녹음은 가능하나 상대방 사전 고지(안내 멘트) 권장 (통신비밀보호법)
- **개인정보:** 민원·녹음·학생/학부모 정보는 민감정보 준하여 암호화 저장, 보관·파기 정책·수집 동의 필요
- **안심번호(F6):** 실번호 비노출은 통신사/제3자 가상번호 중계로만 구현 → 사업자 계약·비용 사전 확인
- **AI 한계:** 자동 필터가 정당한 민원을 오차단하지 않도록 **사람 재검토·이의/에스컬레이션 경로(F8) 필수**
- **데이터 주권:** 교육·공공 성격상 국내 리전/클라우드 우선 검토

---

## 📊 현재 상태

**Phase 1 MVP + Phase 2 전체 완료** — 접수부터 이관까지 엔드투엔드로 돌아갑니다.

- ✅ **인증·권한**: 회원가입/로그인(JWT), 역할별 라우트 가드, 건별 열람 통제
- ✅ **F1 분류**: 접수 시 카테고리 자동 분류 → 단순 행정은 `auto_answered`
- ✅ **자동 응대 게이트**: 신뢰도·위험도·안전 키워드를 교차 검증해, 확신 없는 건은
  챗봇에 맡기지 않고 교사에게 보냄 (오분류 비용이 비대칭이므로 자동 응대 쪽으로만 보수적)
- ✅ **F2 위험**: 감정·공격성 → 위험도(low~critical) 기록
- ✅ **F3 욕설·위협 필터**: 결정론적 규칙 기반 차단 + 원문 증거 보관(교사 미노출).
  폭력을 *신고하는* 민원이 오차단되지 않도록 회귀 테스트로 고정
- ✅ **자동 라우팅**: `teacher_assignments` 기반 담당 교사 배정
- ✅ **F4 답변 초안**: F5 유사 사례를 근거로 주입해 생성, 초안 이력 보관
- ✅ **F5 유사 사례(RAG)**: pgvector 코사인 검색 + 지식베이스 관리
- ✅ **F8 MDT 이관**: 이관 요청 → 접수 → 해결/반송, 민원 상태 연동
- ✅ **F9 대시보드**: 카테고리·위험도·상태별 집계
- ✅ **Celery 워커**: 사례 임베딩 배치 인덱싱, F7 STT 변환 태스크
- ✅ **테스트 149건**: 안전 판정 경로(게이트·F3 필터)와 데이터·평가 도구 회귀 고정
  — `cd backend && pytest` (DB 불필요, 0.5초)
- ✅ **F1 자체 모델 기반**: 합성 민원 생성기 + 평가 하네스(정확도 + 안전 지표) + 기준선
- ✅ 프론트/백엔드 계약을 camelCase로 통일(`@sotong/shared`와 일치)

**남은 것**: API 라우트·워커 테스트, Alembic 마이그레이션, `audit_logs` 기록,
챗봇 자동 응대 실체화, 학부모 동선(`parent_id` 연결), 프론트 반응형·목록 필터,
F6 안심번호(외부 사업자 연동 필요), F7 녹음 수집·재생 UI.

키가 없어도 앱은 뜹니다 — `ANTHROPIC_API_KEY` 없으면 F1·F2·F4가 규칙 기반 fallback으로,
`EMBEDDING_API_KEY` 없으면 F5가 결정론적 해싱 임베딩으로 동작합니다.

> 📋 **기능별 검증 수준·알려진 갭·다음 우선순위는 [`docs/development-status.md`](docs/development-status.md) 참고.**
> (챗봇 자동 응대 미실체화, 학부모 동선 부재, API 테스트 부재 등 실제 갭과
> F1 분류기 기준선을 정리해 두었습니다.)

백엔드 상세는 [`backend/README.md`](backend/README.md) 참고.
