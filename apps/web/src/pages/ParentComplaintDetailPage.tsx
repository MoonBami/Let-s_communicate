import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { CATEGORY_LABEL } from '@sotong/shared';
import { api } from '@/lib/api';
import {
  parentComplaintDetailPath,
  type ParentComplaintSummary,
} from '@/lib/parentComplaints';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { ParentComplaintTimeline } from '@/components/parent/ParentComplaintTimeline';
import { parentStatusMeta } from '@/components/parent/complaintStatus';

const dateTimeFormatter = new Intl.DateTimeFormat('ko-KR', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

export function ParentComplaintDetailPage() {
  const { id = '' } = useParams();
  const complaint = useQuery({
    queryKey: ['parent-complaint', id],
    queryFn: async () => {
      const { data } = await api.get<ParentComplaintSummary>(parentComplaintDetailPath(id));
      return data;
    },
    enabled: id.length > 0,
    retry: false,
  });

  if (complaint.isLoading) {
    return <ParentDetailSkeleton />;
  }

  if (complaint.isError || !complaint.data) {
    return (
      <div className="space-y-5">
        <BackToParentDashboard />
        <EmptyState
          title="민원 내용을 불러올 수 없습니다"
          description="본인 민원 상세 조회 기능이 준비 중이거나 접근할 수 없는 민원입니다."
          action={
            <button
              type="button"
              onClick={() => complaint.refetch()}
              className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-emerald-700"
            >
              다시 시도
            </button>
          }
        />
      </div>
    );
  }

  const item = complaint.data;
  const status = parentStatusMeta[item.status];

  return (
    <div className="space-y-6">
      <BackToParentDashboard />

      <header className="rounded-2xl border border-emerald-100 bg-white p-5 shadow-sm shadow-emerald-100/40 sm:p-7">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={status.tone}>{status.label}</Badge>
          {item.category && <Badge>{CATEGORY_LABEL[item.category]}</Badge>}
        </div>
        <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
          {item.title?.trim() || '제목 없는 민원'}
        </h1>
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs font-medium text-slate-500">
          <span>접수 {dateTimeFormatter.format(new Date(item.createdAt))}</span>
          <span>최근 변경 {dateTimeFormatter.format(new Date(item.updatedAt))}</span>
        </div>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
            <svg viewBox="0 0 24 24" fill="none" className="size-5" aria-hidden="true">
              <path d="M12 7v5l3 2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
            </svg>
          </span>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">현재 처리 상황</p>
            <h2 className="mt-1 text-lg font-bold text-slate-950">{status.label}</h2>
            <p className="mt-1 text-sm leading-6 text-slate-600">{status.description}</p>
          </div>
        </div>

        <div className="mt-7 border-t border-slate-100 pt-6">
          <ParentComplaintTimeline status={item.status} />
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
        <h2 className="text-base font-bold text-slate-950">접수한 내용</h2>
        <p className="mt-4 whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm leading-7 text-slate-700">
          {item.body}
        </p>
      </section>

      <section className="rounded-2xl border border-emerald-100 bg-emerald-50 p-5 sm:flex sm:items-center sm:justify-between sm:gap-5">
        <div>
          <h2 className="font-bold text-emerald-950">진행 상황은 이 화면에서 확인할 수 있습니다</h2>
          <p className="mt-1 text-sm leading-6 text-emerald-800">
            담당자의 내부 검토 정보는 보호되며, 학부모님께 필요한 처리 단계와 결과만 안내됩니다.
          </p>
        </div>
        <Link
          to="/parent/new"
          className="mt-4 inline-flex shrink-0 rounded-xl border border-emerald-200 bg-white px-4 py-2.5 text-sm font-bold text-emerald-700 transition hover:border-emerald-300 sm:mt-0"
        >
          새 민원 접수
        </Link>
      </section>
    </div>
  );
}

function BackToParentDashboard() {
  return (
    <Link
      to="/parent"
      className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 transition hover:text-emerald-700"
    >
      <svg viewBox="0 0 24 24" fill="none" className="size-4" aria-hidden="true">
        <path d="m15 5-7 7 7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      내 민원으로
    </Link>
  );
}

function ParentDetailSkeleton() {
  return (
    <div className="animate-pulse space-y-6" aria-label="민원 상세를 불러오는 중" aria-busy="true">
      <div className="h-5 w-24 rounded bg-slate-200" />
      <div className="rounded-2xl border border-slate-200 bg-white p-7">
        <div className="h-6 w-20 rounded-full bg-slate-100" />
        <div className="mt-5 h-8 w-1/2 rounded bg-slate-100" />
        <div className="mt-4 h-4 w-1/3 rounded bg-slate-100" />
      </div>
      <div className="h-64 rounded-2xl border border-slate-200 bg-white" />
    </div>
  );
}
