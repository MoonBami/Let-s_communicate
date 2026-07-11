// DB 스키마(db/schema.sql)의 PostgreSQL ENUM과 1:1로 대응하는 공용 상수.
// 웹·모바일·백엔드 계약의 단일 소스. 스키마 변경 시 이 파일도 함께 갱신할 것.

export const USER_ROLE = ['teacher', 'parent', 'admin', 'mdt'] as const;
export type UserRole = (typeof USER_ROLE)[number];

export const COMPLAINT_CHANNEL = ['web_form', 'chat', 'call'] as const;
export type ComplaintChannel = (typeof COMPLAINT_CHANNEL)[number];

export const COMPLAINT_CATEGORY = [
  'administrative', // 단순 행정
  'learning', // 학습 지도
  'life', // 생활
  'grades', // 성적
  'violence_dispute', // 학교폭력·분쟁
  'other',
] as const;
export type ComplaintCategory = (typeof COMPLAINT_CATEGORY)[number];

export const COMPLAINT_STATUS = [
  'received',
  'auto_answered',
  'filtered_blocked',
  'pending_teacher',
  'in_progress',
  'answered',
  'escalated',
  'closed',
] as const;
export type ComplaintStatus = (typeof COMPLAINT_STATUS)[number];

export const RISK_LEVEL = ['low', 'medium', 'high', 'critical'] as const;
export type RiskLevel = (typeof RISK_LEVEL)[number];

export const ESCALATION_STATUS = ['requested', 'accepted', 'resolved', 'rejected'] as const;
export type EscalationStatus = (typeof ESCALATION_STATUS)[number];

export const RESERVATION_STATUS = ['requested', 'confirmed', 'completed', 'canceled'] as const;
export type ReservationStatus = (typeof RESERVATION_STATUS)[number];

export const CALL_STATUS = ['ringing', 'connected', 'missed', 'ended', 'blocked'] as const;
export type CallStatus = (typeof CALL_STATUS)[number];

// 한국어 라벨 (UI 표시용)
export const CATEGORY_LABEL: Record<ComplaintCategory, string> = {
  administrative: '단순 행정',
  learning: '학습 지도',
  life: '생활',
  grades: '성적',
  violence_dispute: '학교폭력·분쟁',
  other: '기타',
};

export const STATUS_LABEL: Record<ComplaintStatus, string> = {
  received: '접수됨',
  auto_answered: '자동 응대 완료',
  filtered_blocked: '차단됨(증거 보관)',
  pending_teacher: '교사 확인 대기',
  in_progress: '처리 중',
  answered: '답변 완료',
  escalated: 'MDT 이관',
  closed: '종료',
};

export const RISK_LABEL: Record<RiskLevel, string> = {
  low: '낮음',
  medium: '보통',
  high: '높음',
  critical: '긴급',
};
