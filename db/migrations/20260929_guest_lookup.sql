-- 비회원 민원 조회(접수번호 + 숫자 4자리 비밀번호)와 교사 답변을 위한 변경.
-- 20260929_school_code.sql 다음에 실행한다. 여러 번 실행해도 안전하다(IF NOT EXISTS).
-- 새로 만드는 DB 는 schema.sql 에 이미 반영되어 있으므로 실행할 필요가 없다.

ALTER TABLE complaints ADD COLUMN IF NOT EXISTS receipt_code VARCHAR(16);
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS lookup_pin_hash VARCHAR(255);
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS lookup_fail_count INT NOT NULL DEFAULT 0;
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS lookup_locked_until TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS complaints_receipt_code_key ON complaints(receipt_code);

-- 교사 답변 저장소. 초기 schema.sql 에 이미 있던 테이블이라 대부분의 DB 에는 존재한다.
CREATE TABLE IF NOT EXISTS complaint_messages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id  UUID NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    sender_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    is_ai         BOOLEAN NOT NULL DEFAULT FALSE,
    body          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_complaint_messages_complaint ON complaint_messages(complaint_id, created_at);
