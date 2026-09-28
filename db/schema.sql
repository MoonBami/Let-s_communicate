-- =============================================================================
--  「소통해요」 교사 민원 보조 AI 시스템 — 데이터베이스 스키마
--  DBMS : PostgreSQL 15+ (pgvector 확장 사용)
--  작성 : 개발 기획 회의 기준 (MVP → 확장 단계 전체 커버)
--
--  기능 매핑
--    F1 민원 자동 분류/라우팅   F2 감정·위험 탐지      F3 욕설·위협 필터/증거
--    F4 답변 초안·상담 템플릿    F5 유사 사례 검색(RAG) F6 안심번호·예약 상담
--    F7 실시간 녹음·STT          F8 MDT 이관            F9 관리자 통계 대시보드
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 0. 확장 (Extensions)
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- 임베딩 유사도 검색 (F5)


-- ---------------------------------------------------------------------------
-- 1. 공통 ENUM 타입
-- ---------------------------------------------------------------------------
CREATE TYPE user_role         AS ENUM ('teacher', 'parent', 'admin', 'mdt');           -- mdt = 민원대응팀
CREATE TYPE complaint_channel AS ENUM ('web_form', 'chat', 'call');
CREATE TYPE complaint_category AS ENUM (
    'administrative',   -- 단순 행정
    'learning',         -- 학습 지도
    'life',             -- 생활
    'grades',           -- 성적
    'violence_dispute', -- 학교폭력·분쟁
    'other'
);
CREATE TYPE complaint_status AS ENUM (
    'received',          -- 접수됨 (AI 처리 전)
    'auto_answered',     -- 챗봇 자동 응대 완료 (단순 행정)
    'filtered_blocked',  -- 욕설·위협으로 차단(교사 미노출) → 증거 보관
    'pending_teacher',   -- 필터 통과, 교사 확인 대기
    'in_progress',       -- 교사 처리 중
    'answered',          -- 답변 완료
    'escalated',         -- MDT/관리자 이관
    'closed'             -- 종료
);
CREATE TYPE risk_level        AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE escalation_status AS ENUM ('requested', 'accepted', 'resolved', 'rejected');
CREATE TYPE reservation_status AS ENUM ('requested', 'confirmed', 'completed', 'canceled');
CREATE TYPE call_status       AS ENUM ('ringing', 'connected', 'missed', 'ended', 'blocked');


-- ---------------------------------------------------------------------------
-- 공통: updated_at 자동 갱신 트리거 함수
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ===========================================================================
-- 2. 조직 · 사용자
-- ===========================================================================

-- 학교
CREATE TABLE schools (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code         VARCHAR(20) UNIQUE,           -- 학교 코드(학부모가 입력해 학교를 찾는 공개 식별자)
    name         VARCHAR(150) NOT NULL,
    edu_office   VARCHAR(100),                 -- 관할 교육청
    address      VARCHAR(255),
    phone        VARCHAR(30),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 사용자 (인증 공통 계정) — 교사·학부모·관리자·MDT
CREATE TABLE users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id      UUID REFERENCES schools(id) ON DELETE SET NULL,
    role           user_role NOT NULL,
    email          VARCHAR(255) UNIQUE,
    phone          VARCHAR(30),                -- 실제 번호(민감) — 접근 통제 대상
    password_hash  VARCHAR(255),               -- 소셜/교원 인증 시 NULL 가능
    name           VARCHAR(100) NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at  TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_school ON users(school_id);
CREATE INDEX idx_users_role   ON users(role);

-- 교사 프로필 (근무 시간 외 알림 차단 설정 포함 — F6)
CREATE TABLE teacher_profiles (
    user_id          UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    subject          VARCHAR(100),             -- 담당 과목
    grade            SMALLINT,                 -- 담당 학년
    class_name       VARCHAR(50),              -- 담당 반
    work_start       TIME NOT NULL DEFAULT '09:00',   -- 근무 시작
    work_end         TIME NOT NULL DEFAULT '17:00',   -- 근무 종료
    block_after_hours BOOLEAN NOT NULL DEFAULT TRUE,  -- 근무시간 외 알림 자동 차단
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 학생
CREATE TABLE students (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id   UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    grade       SMALLINT,
    class_name  VARCHAR(50),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_students_school ON students(school_id);
-- 민원 접수 시 학교 안에서 이름·학년·반으로 학생을 찾는다(services/directory.py).
CREATE INDEX idx_students_lookup ON students(school_id, grade, class_name, name);

-- 보호자(학부모) - 학생 관계
CREATE TABLE guardianships (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    student_id   UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    relationship VARCHAR(30),                  -- 부/모/기타
    UNIQUE (parent_id, student_id)
);

-- 교사 - 학생/반 담당 관계 (민원 라우팅 대상 결정)
CREATE TABLE teacher_assignments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    student_id  UUID REFERENCES students(id) ON DELETE CASCADE,
    grade       SMALLINT,
    class_name  VARCHAR(50),
    UNIQUE (teacher_id, student_id)
);


-- ===========================================================================
-- 3. 민원 (핵심)
-- ===========================================================================

CREATE TABLE complaints (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id       UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    parent_id       UUID REFERENCES users(id) ON DELETE SET NULL,      -- 신청 학부모
    student_id      UUID REFERENCES students(id) ON DELETE SET NULL,   -- 관련 학생
    assigned_teacher_id UUID REFERENCES users(id) ON DELETE SET NULL,  -- 배정 교사(라우팅 결과)
    channel         complaint_channel NOT NULL DEFAULT 'web_form',
    title           VARCHAR(255),
    body            TEXT NOT NULL,             -- 원문 (필터 전 원본)
    category        complaint_category,        -- F1 분류 결과 (확정)
    status          complaint_status NOT NULL DEFAULT 'received',
    risk            risk_level DEFAULT 'low',  -- F2 위험도 요약
    is_auto_handled BOOLEAN NOT NULL DEFAULT FALSE,  -- 챗봇 자동 응대 여부
    filtered        BOOLEAN NOT NULL DEFAULT FALSE,  -- F3 필터 차단 여부
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ
);
CREATE INDEX idx_complaints_teacher  ON complaints(assigned_teacher_id);
CREATE INDEX idx_complaints_parent   ON complaints(parent_id);
CREATE INDEX idx_complaints_status   ON complaints(status);
CREATE INDEX idx_complaints_category ON complaints(category);
CREATE INDEX idx_complaints_created  ON complaints(created_at);

CREATE TRIGGER trg_complaints_updated
    BEFORE UPDATE ON complaints
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 민원 대화 스레드 (채팅/챗봇 자동응대 메시지)
CREATE TABLE complaint_messages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id  UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    sender_id     UUID REFERENCES users(id) ON DELETE SET NULL,  -- NULL = AI/챗봇
    is_ai         BOOLEAN NOT NULL DEFAULT FALSE,
    body          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_messages_complaint ON complaint_messages(complaint_id);


-- ===========================================================================
-- 4. AI 처리 결과
-- ===========================================================================

-- F1: 자동 분류 결과 (모델/버전별 이력 보관)
CREATE TABLE classifications (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id   UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    predicted      complaint_category NOT NULL,
    confidence     NUMERIC(5,4),              -- 0.0000 ~ 1.0000
    model_name     VARCHAR(100),             -- 예: claude / gpt-4o / koelectra-v2
    model_version  VARCHAR(50),
    is_auto_routed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_classification_complaint ON classifications(complaint_id);

-- F2: 감정 분석 · 위험 탐지
CREATE TABLE risk_analyses (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id     UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    sentiment_score  NUMERIC(5,4),           -- -1(부정) ~ +1(긍정)
    aggression_score NUMERIC(5,4),           -- 0 ~ 1 공격성
    risk             risk_level NOT NULL,
    reasons          JSONB,                  -- 탐지 근거(키워드/설명)
    model_name       VARCHAR(100),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_risk_complaint ON risk_analyses(complaint_id);

-- F3: 욕설·위협 필터 로그 및 증거 기록 (교사 미노출 원문 보관)
CREATE TABLE content_filter_logs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id   UUID REFERENCES complaints(id) ON DELETE CASCADE,
    message_id     UUID REFERENCES complaint_messages(id) ON DELETE CASCADE,
    is_blocked     BOOLEAN NOT NULL DEFAULT TRUE,
    matched_terms  JSONB,                    -- 탐지된 욕설/위협 표현
    severity       risk_level NOT NULL DEFAULT 'medium',
    raw_evidence   TEXT NOT NULL,            -- 원문(증빙). 접근 통제·암호화 권장
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_filter_complaint ON content_filter_logs(complaint_id);


-- ===========================================================================
-- 5. 답변 지원 (F4 · F5)
-- ===========================================================================

-- F4: 상담 가이드라인 / 공지·답변 표준 템플릿
CREATE TABLE response_templates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id   UUID REFERENCES schools(id) ON DELETE CASCADE,  -- NULL = 전역 공용
    category    complaint_category,
    title       VARCHAR(200) NOT NULL,
    body        TEXT NOT NULL,
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_templates_category ON response_templates(category);

-- F4: AI 답변 초안
CREATE TABLE answer_drafts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id  UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    template_id   UUID REFERENCES response_templates(id) ON DELETE SET NULL,
    draft_body    TEXT NOT NULL,
    model_name    VARCHAR(100),
    is_adopted    BOOLEAN NOT NULL DEFAULT FALSE,  -- 교사가 채택했는지
    edited_body   TEXT,                            -- 교사 최종 수정본
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_drafts_complaint ON answer_drafts(complaint_id);

-- F5: 유사 사례 지식베이스 (과거 민원-대응 사례)
CREATE TABLE complaint_cases (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_complaint_id UUID REFERENCES complaints(id) ON DELETE SET NULL,
    category       complaint_category,
    summary        TEXT NOT NULL,            -- 사례 요약
    resolution     TEXT NOT NULL,            -- 대응 방식
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- F5: 사례 임베딩 (RAG 검색)  — 차원은 사용 임베딩 모델에 맞춰 조정
CREATE TABLE case_embeddings (
    case_id     UUID PRIMARY KEY REFERENCES complaint_cases(id) ON DELETE CASCADE,
    embedding   VECTOR(1536) NOT NULL,       -- 예: OpenAI text-embedding-3-small
    model_name  VARCHAR(100),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 코사인 유사도 근사 검색용 인덱스
CREATE INDEX idx_case_embedding ON case_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


-- ===========================================================================
-- 6. 안심번호 · 예약 · 통화 (F6)
-- ===========================================================================

-- 안심(가상)번호 매핑 — 교사 실번호 비노출
CREATE TABLE safe_numbers (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    virtual_number VARCHAR(30) NOT NULL UNIQUE,   -- 050 등 가상번호
    provider      VARCHAR(50),                    -- 통신사/제3자 사업자
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 상담 예약
CREATE TABLE consultation_reservations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    student_id    UUID REFERENCES students(id) ON DELETE SET NULL,
    scheduled_at  TIMESTAMPTZ NOT NULL,
    status        reservation_status NOT NULL DEFAULT 'requested',
    memo          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reservation_teacher ON consultation_reservations(teacher_id);

-- 통화 세션 (안심번호 중계 통화)
CREATE TABLE call_sessions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_id UUID REFERENCES consultation_reservations(id) ON DELETE SET NULL,
    teacher_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    safe_number_id UUID REFERENCES safe_numbers(id) ON DELETE SET NULL,
    status         call_status NOT NULL DEFAULT 'ringing',
    started_at     TIMESTAMPTZ,
    ended_at       TIMESTAMPTZ,
    duration_sec   INTEGER,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_call_teacher ON call_sessions(teacher_id);


-- ===========================================================================
-- 7. 녹음 · 텍스트 변환 (F7)
-- ===========================================================================

CREATE TABLE recordings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_session_id UUID REFERENCES call_sessions(id) ON DELETE CASCADE,
    complaint_id   UUID REFERENCES complaints(id) ON DELETE SET NULL,
    storage_url    VARCHAR(500) NOT NULL,     -- 암호화 저장된 오디오 위치(S3 등)
    duration_sec   INTEGER,
    consent_given  BOOLEAN NOT NULL DEFAULT FALSE,  -- 녹음 고지·동의 여부
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE transcripts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recording_id UUID NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    full_text    TEXT NOT NULL,              -- STT 전체 대화록
    segments     JSONB,                      -- [{speaker, start, end, text}, ...]
    stt_provider VARCHAR(50),                -- CLOVA / Whisper / RTZR
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_transcript_recording ON transcripts(recording_id);


-- ===========================================================================
-- 8. 민원대응팀(MDT) 이관 (F8)
-- ===========================================================================

CREATE TABLE escalations (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id   UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    requested_by   UUID REFERENCES users(id) ON DELETE SET NULL,  -- 이관 요청 교사
    assigned_to    UUID REFERENCES users(id) ON DELETE SET NULL,  -- MDT/관리자
    status         escalation_status NOT NULL DEFAULT 'requested',
    reason         TEXT,
    resolution     TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at    TIMESTAMPTZ
);
CREATE INDEX idx_escalation_complaint ON escalations(complaint_id);
CREATE INDEX idx_escalation_status    ON escalations(status);


-- ===========================================================================
-- 9. 알림 · 감사 로그
-- ===========================================================================

-- 알림 (근무시간 외 차단 로직은 애플리케이션에서 teacher_profiles 참조)
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    complaint_id UUID REFERENCES complaints(id) ON DELETE CASCADE,
    type        VARCHAR(50) NOT NULL,        -- new_complaint / escalation / reservation ...
    title       VARCHAR(200) NOT NULL,
    body        TEXT,
    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    is_blocked  BOOLEAN NOT NULL DEFAULT FALSE,  -- 근무시간 외 차단되어 보류됨
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notification_user ON notifications(user_id, is_read);

-- 감사 로그 (민감 데이터 접근 추적 — 녹음/증거/개인정보)
CREATE TABLE audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(100) NOT NULL,       -- VIEW_RECORDING / EXPORT_EVIDENCE ...
    entity_type VARCHAR(50),
    entity_id   UUID,
    ip_address  INET,
    detail      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_user   ON audit_logs(user_id);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);


-- ===========================================================================
-- 10. 통계 대시보드 뷰 (F9)
-- ===========================================================================

-- 학교별·카테고리별·위험도별 민원 집계 (대시보드 기초 뷰)
CREATE VIEW v_complaint_stats AS
SELECT
    school_id,
    category,
    risk,
    status,
    date_trunc('day', created_at) AS day,
    COUNT(*)                      AS total
FROM complaints
GROUP BY school_id, category, risk, status, date_trunc('day', created_at);

-- 교사별 처리 현황
CREATE VIEW v_teacher_workload AS
SELECT
    assigned_teacher_id AS teacher_id,
    COUNT(*) FILTER (WHERE status IN ('pending_teacher','in_progress')) AS open_count,
    COUNT(*) FILTER (WHERE status = 'answered')                          AS answered_count,
    COUNT(*) FILTER (WHERE status = 'escalated')                         AS escalated_count
FROM complaints
WHERE assigned_teacher_id IS NOT NULL
GROUP BY assigned_teacher_id;

-- =============================================================================
--  END OF SCHEMA
-- =============================================================================
