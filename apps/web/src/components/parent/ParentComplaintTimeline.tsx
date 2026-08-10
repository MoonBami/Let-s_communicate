import type { ComplaintStatus } from '@sotong/shared';
import { parentStatusMeta } from './complaintStatus';

const stages = [
  { title: '접수 완료', description: '민원 내용을 안전하게 접수했습니다.' },
  { title: '내용 확인', description: '담당자 배정과 내용을 확인합니다.' },
  { title: '답변 준비', description: '필요한 사항을 검토하고 답변을 준비합니다.' },
  { title: '처리 완료', description: '처리 결과와 답변을 확인할 수 있습니다.' },
] as const;

export function ParentComplaintTimeline({ status }: { status: ComplaintStatus }) {
  const currentStep = parentStatusMeta[status].step;

  return (
    <ol className="grid gap-4 sm:grid-cols-4" aria-label="민원 처리 단계">
      {stages.map((stage, index) => {
        const step = index + 1;
        const isComplete = step < currentStep;
        const isCurrent = step === currentStep;

        return (
          <li key={stage.title} className="relative flex gap-3 sm:block">
            {index < stages.length - 1 && (
              <span
                className={`absolute left-4 top-8 h-[calc(100%+1rem)] w-px sm:left-8 sm:top-4 sm:h-px sm:w-[calc(100%-1rem)] ${
                  isComplete ? 'bg-emerald-400' : 'bg-slate-200'
                }`}
                aria-hidden="true"
              />
            )}
            <span
              className={`relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ring-4 ring-white sm:mb-3 ${
                isComplete
                  ? 'bg-emerald-500 text-white'
                  : isCurrent
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-100 text-slate-400'
              }`}
              aria-current={isCurrent ? 'step' : undefined}
            >
              {isComplete ? (
                <svg viewBox="0 0 24 24" fill="none" className="size-4" aria-hidden="true">
                  <path d="m6 12 4 4 8-9" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                step
              )}
            </span>
            <div className="pb-3 sm:pr-3">
              <p className={`text-sm font-bold ${isCurrent ? 'text-emerald-700' : 'text-slate-800'}`}>
                {stage.title}
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">{stage.description}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
