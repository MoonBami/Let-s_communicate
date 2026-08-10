import type { ComplaintStatus } from '@sotong/shared';
import type { BadgeTone } from '@/components/ui/Badge';

interface ParentStatusMeta {
  label: string;
  description: string;
  step: 1 | 2 | 3 | 4;
  tone: BadgeTone;
}

export const parentStatusMeta: Record<ComplaintStatus, ParentStatusMeta> = {
  received: {
    label: '접수 완료',
    description: '민원이 정상적으로 접수되었습니다.',
    step: 1,
    tone: 'brand',
  },
  filtered_blocked: {
    label: '내용 확인 중',
    description: '안전한 전달을 위해 담당 부서에서 내용을 확인하고 있습니다.',
    step: 2,
    tone: 'warning',
  },
  pending_teacher: {
    label: '담당자 확인 중',
    description: '담당 교사가 접수 내용을 확인하고 있습니다.',
    step: 2,
    tone: 'warning',
  },
  in_progress: {
    label: '처리 중',
    description: '담당자가 필요한 내용을 확인하고 답변을 준비하고 있습니다.',
    step: 3,
    tone: 'warning',
  },
  escalated: {
    label: '전문 담당팀 검토 중',
    description: '보다 정확한 처리를 위해 전문 담당팀이 함께 검토하고 있습니다.',
    step: 3,
    tone: 'warning',
  },
  auto_answered: {
    label: '안내 완료',
    description: '문의 내용에 대한 안내가 완료되었습니다.',
    step: 4,
    tone: 'success',
  },
  answered: {
    label: '답변 도착',
    description: '담당자의 답변이 등록되었습니다.',
    step: 4,
    tone: 'success',
  },
  closed: {
    label: '처리 완료',
    description: '민원 처리가 모두 완료되었습니다.',
    step: 4,
    tone: 'success',
  },
};
