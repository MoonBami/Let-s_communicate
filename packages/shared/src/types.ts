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

/** 학교 코드 조회 결과 (공개 정보만) */
export interface SchoolPublic {
  id: string;
  code: string;
  name: string;
  eduOffice: string | null;
}

/** 학부모가 입력한 학생 정보 — 서버가 학교 안에서 학생을 찾는다.
 *  찾았는지 여부는 응답에 드러나지 않는다(studentId·assignedTeacherId 가 비어서 온다). */
export interface StudentLookup {
  name: string;
  grade: number;
  className: string;
}

/** 학부모 민원 접수 요청 (F1 진입점). studentId 와 student 는 둘 중 하나만. */
export interface CreateComplaintRequest {
  schoolId: string;
  studentId?: string;
  student?: StudentLookup;
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

/** 교사 회원가입 요청. 관리자 계정은 가입으로 만들 수 없다(운영자가 생성). */
export interface SignupRequest {
  email: string;
  password: string;
  name: string;
  role: Extract<UserRole, 'teacher'>;
}

/** 교사 담당 반·학생 배정 */
export interface TeacherAssignment {
  id: string;
  teacherId: string;
  studentId: string | null;
  grade: number | null;
  className: string | null;
}

/** 관리자 배정 화면의 교사 요약. schoolId 가 null 이면 갓 가입한 미소속 교사. */
export interface TeacherSummary {
  id: string;
  name: string;
  email: string | null;
  schoolId: string | null;
  isActive: boolean;
  assignments: TeacherAssignment[];
  openComplaints: number;
}

export interface AssignClassRequest {
  teacherId: string;
  grade: number;
  className: string;
  /** 이 반 학생의 진행 중 민원을 새 담당에게 옮길지 */
  transferOpen: boolean;
}

export interface AssignClassResult {
  assignment: TeacherAssignment;
  replaced: number;
  movedComplaints: number;
}

export interface AssignComplaintRequest {
  teacherId: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
