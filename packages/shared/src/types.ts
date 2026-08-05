// 도메인 DTO 타입 (API 요청/응답 계약). 웹·모바일 공용.

import type {
  ComplaintCategory,
  ComplaintChannel,
  ComplaintStatus,
  EscalationStatus,
  RiskLevel,
  UserRole,
} from './enums';

export interface User {
  id: string;
  schoolId: string | null;
  role: UserRole;
  email: string | null;
  name: string;
  isActive: boolean;
}

export interface Complaint {
  id: string;
  schoolId: string;
  parentId: string | null;
  studentId: string | null;
  assignedTeacherId: string | null;
  channel: ComplaintChannel;
  title: string | null;
  body: string;
  category: ComplaintCategory | null;
  status: ComplaintStatus;
  risk: RiskLevel;
  isAutoHandled: boolean;
  filtered: boolean;
  createdAt: string;
  updatedAt: string;
  closedAt: string | null;
}

/** 학부모 민원 접수 요청 (F1 진입점) */
export interface CreateComplaintRequest {
  schoolId: string;
  studentId?: string;
  channel?: ComplaintChannel;
  title?: string;
  body: string;
}

/** F1 분류 결과 */
export interface Classification {
  predicted: ComplaintCategory;
  confidence: number | null; // 0.0 ~ 1.0
  modelName: string | null;
  isAutoRouted: boolean;
}

/** F2 감정·위험 분석 결과 */
export interface RiskAnalysis {
  sentimentScore: number | null; // -1 ~ 1
  aggressionScore: number | null; // 0 ~ 1
  risk: RiskLevel;
  reasons: string[]; // 위험 판단 근거
  modelName: string | null;
}

/** 민원 상세 — 목록(Complaint)에 최신 분류·위험 분석을 덧붙인 형태 */
export interface ComplaintDetail extends Complaint {
  classification: Classification | null;
  riskAnalysis: RiskAnalysis | null;
}

/** F4 답변 초안 */
export interface AnswerDraft {
  id: string;
  complaintId: string;
  draftBody: string;
  modelName: string | null;
  isAdopted: boolean;
  editedBody: string | null;
  createdAt: string;
}

/** F5 유사 사례 검색 결과 */
export interface SimilarCase {
  caseId: string;
  category: ComplaintCategory | null;
  summary: string;
  resolution: string;
  similarity: number; // 0~1 코사인 유사도
}

/** F5 지식베이스 사례 */
export interface ComplaintCase {
  id: string;
  sourceComplaintId: string | null;
  category: ComplaintCategory | null;
  summary: string;
  resolution: string;
  createdAt: string;
}

export interface CreateCaseRequest {
  sourceComplaintId?: string;
  category?: ComplaintCategory;
  summary: string;
  resolution: string;
}

/** F8 MDT 이관 */
export interface Escalation {
  id: string;
  complaintId: string;
  requestedBy: string | null;
  assignedTo: string | null;
  status: EscalationStatus;
  reason: string | null;
  resolution: string | null;
  createdAt: string;
  resolvedAt: string | null;
}

export interface CreateEscalationRequest {
  complaintId: string;
  reason: string;
}

export interface UpdateEscalationRequest {
  status: Extract<EscalationStatus, 'accepted' | 'resolved' | 'rejected'>;
  resolution?: string;
}

/** F9 대시보드 집계 한 줄 */
export interface ComplaintStat {
  category: ComplaintCategory | null;
  risk: RiskLevel;
  status: ComplaintStatus;
  day: string;
  total: number;
}

export interface AuthTokens {
  accessToken: string;
  tokenType: 'bearer';
}

export interface LoginRequest {
  email: string;
  password: string;
}

/** 교사·관리자 회원가입 요청 */
export interface SignupRequest {
  email: string;
  password: string;
  name: string;
  role: Extract<UserRole, 'teacher' | 'admin'>;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
