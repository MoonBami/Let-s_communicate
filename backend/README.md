# 소통해요 Backend (FastAPI)

## 실행

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# bash:              source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # 값 채우기
uvicorn app.main:app --reload --port 8000
```

- API 문서(Swagger): http://localhost:8000/docs
- 헬스체크: http://localhost:8000/health

> `ANTHROPIC_API_KEY`를 비워두면 AI 서비스가 **규칙 기반 fallback**으로 동작해
> 키 없이도 앱이 뜹니다(F1 키워드 분류 / F4 템플릿 답변).

## 구조

```
app/
├─ main.py            # FastAPI 엔트리 + CORS
├─ core/              # config(env), security(JWT/bcrypt)
├─ db/session.py      # SQLAlchemy 엔진·세션·Base
├─ models/            # ORM 모델 (대표: user, complaint) ← db/schema.sql 기준 확장
├─ schemas/           # Pydantic 입출력 스키마
├─ api/
│  ├─ deps.py         # get_current_user 등 의존성
│  └─ routes/         # auth · complaints(F1/F4) · dashboard(F9)
└─ services/ai/       # classifier(F1) · drafter(F4) · client(Anthropic 래퍼)
```

## DB

`../db/schema.sql`을 PostgreSQL 15+(pgvector)에 적용. 현재 ORM 모델은 대표 테이블만
스캐폴딩되어 있으니, 나머지는 스키마를 참조해 같은 패턴으로 추가하세요.
운영 전환 시 **Alembic** 도입 권장(`alembic init`).

## 다음 채울 곳 (TODO)

- [ ] F2 위험 탐지 · F3 욕설 필터를 접수 파이프라인(`routes/complaints.create_complaint`)에 연결
- [ ] 민원 라우팅: `teacher_assignments` 기반 `assigned_teacher_id` 자동 배정
- [ ] F5 RAG: `complaint_cases` + pgvector 임베딩 검색 → drafter에 주입
- [ ] 사용자 시드/회원가입, 역할별 권한 세분화
- [ ] Celery + Redis 워커 (STT 변환·배치 분석)
