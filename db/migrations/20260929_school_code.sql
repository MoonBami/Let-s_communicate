-- 기존 DB(로컬 볼륨·Neon 등)에 학교 코드 컬럼과 학생 조회 인덱스를 추가한다.
-- 새로 만드는 DB 는 schema.sql 에 이미 반영되어 있으므로 실행할 필요가 없다.
-- 여러 번 실행해도 안전하다(IF NOT EXISTS).
--
--   로컬:  docker cp db/migrations/20260929_school_code.sql sotong-db:/tmp/m.sql
--          docker exec sotong-db psql -U postgres -d sotonghaeyo -f /tmp/m.sql
--   Neon:  콘솔 SQL Editor 에 이 파일 내용을 붙여 넣고 실행

ALTER TABLE schools ADD COLUMN IF NOT EXISTS code VARCHAR(20);
CREATE UNIQUE INDEX IF NOT EXISTS schools_code_key ON schools(code);
CREATE INDEX IF NOT EXISTS idx_students_lookup ON students(school_id, grade, class_name, name);
