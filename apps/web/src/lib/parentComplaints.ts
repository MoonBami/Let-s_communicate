import type { ComplaintCategory, ComplaintStatus } from '@sotong/shared';

export const PARENT_COMPLAINTS_PATH = '/api/parent/complaints';

export const parentComplaintDetailPath = (id: string) => `${PARENT_COMPLAINTS_PATH}/${id}`;

/** 학부모에게 노출해도 되는 최소 민원 정보. 내부 AI 분석 필드는 포함하지 않는다. */
export interface ParentComplaintSummary {
  id: string;
  title: string | null;
  body: string;
  category: ComplaintCategory | null;
  status: ComplaintStatus;
  createdAt: string;
  updatedAt: string;
  closedAt: string | null;
}
