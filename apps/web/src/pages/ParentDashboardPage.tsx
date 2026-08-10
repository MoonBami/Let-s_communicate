import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import type { Paginated } from '@sotong/shared';
import { CATEGORY_LABEL } from '@sotong/shared';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { LoadingCards } from '@/components/ui/LoadingCards';
import { PageHeader } from '@/components/ui/PageHeader';
import { parentStatusMeta } from '@/components/parent/complaintStatus';
import { PARENT_COMPLAINTS_PATH, type ParentComplaintSummary } from '@/lib/parentComplaints';

const dateFormatter = new Intl.DateTimeFormat('ko-KR', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
});

export function ParentDashboardPage() {
  const user = useAuthStore((state) => state.user);
  const complaints = useQuery({
    queryKey: ['parent-complaints'],
    queryFn: async () => {
      const { data } = await api.get<Paginated<ParentComplaintSummary>>(PARENT_COMPLAINTS_PATH);
      return data;
    },
    retry: false,
  });

  const items = complaints.data?.items ?? [];
  const reviewingCount = items.filter((item) =>
    ['received', 'filtered_blocked', 'pending_teacher'].includes(item.status),
  ).length;
  const processingCount = items.filter((item) => ['in_progress', 'escalated'].includes(item.status)).length;
  const completedCount = items.filter((item) =>
    ['auto_answered', 'answered', 'closed'].includes(item.status),
  ).length;

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Parent service"
        title={`${user?.name ?? '학부모'}님, 안녕하세요`}
        description="접수한 민원의 진행 상황과 최근 변경 내용을 확인할 수 있습니다."
        action={
          <Link
            to="/parent/new"
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-emerald-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-emerald-100"
          >
            <svg viewBox="0 0 24 24" fill="none" className="size-4" aria-hidden="true">
              <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            새 민원 접수
          </Link>
        }
      />

      <section className="rounded-2xl border border-emerald-100 bg-gradient-to-r from-emerald-600 to-teal-600 p-5 text-white shadow-lg shadow-emerald-100/70 sm:p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-emerald-100">안심하고 기다려 주세요</p>
            <h2 className="mt-1 text-xl font-bold">민원은 담당자에게 안전하게 전달됩니다</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-emerald-50/90">
              처리 단계가 변경되면 이 화면에서 확인할 수 있습니다. 내부 분석 정보는 노출하지 않고 필요한 진행 상황만 안내합니다.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-3 rounded-xl bg-white/10 px-4 py-3 ring-1 ring-inset ring-white/15">
            <span className="flex size-10 items-center justify-center rounded-full bg-white/15">
              <svg viewBox="0 0 24 24" fill="none" className="size-5" aria-hidden="true">
                <path d="M12 3 5 6v5c0 4.7 2.9 8 7 10 4.1-2 7-5.3 7-10V6l-7-3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
                <path d="m9 12 2 2 4-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <div>
              <p className="text-xs text-emerald-100">개인정보 보호</p>
              <p className="text-sm font-bold">본인 민원만 확인</p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="내 민원 현황">
        <ParentSummary label="전체" value={complaints.data?.total ?? items.length} helper="접수한 민원" />
        <ParentSummary label="내용 확인" value={reviewingCount} helper="담당자 확인 전" />
        <ParentSummary label="처리 중" value={processingCount} helper="답변 준비 중" />
        <ParentSummary label="처리 완료" value={completedCount} helper="안내·답변 완료" complete />
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="font-bold text-slate-950">내 민원</h2>
            <p className="mt-0.5 text-xs text-slate-500">최근 접수한 순서로 표시됩니다.</p>
          </div>
          {complaints.isSuccess && <span className="text-sm font-semibold text-emerald-700">총 {complaints.data.total}건</span>}
        </div>

        <div className="p-4 sm:p-5">
          {complaints.isLoading && <LoadingCards count={2} />}

          {complaints.isError && (
            <EmptyState
              title="내 민원 조회 기능을 연결하고 있습니다"
              description="학부모 본인 민원 조회 API가 준비되면 이곳에 실제 처리 상황이 표시됩니다. 새 민원 접수는 계속 이용할 수 있습니다."
              action={
                <Link
                  to="/parent/new"
                  className="inline-flex rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-emerald-700"
                >
                  민원 접수하기
                </Link>
              }
            />
          )}

          {complaints.isSuccess && items.length > 0 && (
            <div className="space-y-3">
              {items.map((complaint) => (
                <ParentComplaintCard key={complaint.id} complaint={complaint} />
              ))}
            </div>
          )}

          {complaints.isSuccess && items.length === 0 && (
            <EmptyState
              title="아직 접수한 민원이 없습니다"
              description="학교에 전달할 문의가 있다면 새 민원 접수에서 내용을 작성해 주세요."
              action={
                <Link
                  to="/parent/new"
                  className="inline-flex rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-emerald-700"
                >
                  첫 민원 접수하기
                </Link>
              }
            />
          )}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="font-bold text-slate-950">처리는 이렇게 진행됩니다</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <ProcessGuide number="1" title="안전한 접수" description="작성한 내용을 시스템이 안전하게 접수합니다." />
            <ProcessGuide number="2" title="담당자 확인" description="민원 유형에 맞는 담당자가 내용을 확인합니다." />
            <ProcessGuide number="3" title="처리 결과 안내" description="진행 상태와 답변 등록 여부를 알려드립니다." />
          </div>
        </div>
        <div className="rounded-2xl border border-amber-100 bg-amber-50 p-5">
          <p className="text-xs font-bold uppercase tracking-wider text-amber-700">안내</p>
          <h2 className="mt-2 font-bold text-amber-950">긴급한 안전 문제인가요?</h2>
          <p className="mt-2 text-sm leading-6 text-amber-800">
            즉각적인 신변 위협이나 학교폭력 긴급 상황은 민원 답변을 기다리지 말고 학교 또는 관계 기관에 바로 연락해 주세요.
          </p>
        </div>
      </section>
    </div>
  );
}

function ParentSummary({
  label,
  value,
  helper,
  complete = false,
}: {
  label: string;
  value: number;
  helper: string;
  complete?: boolean;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/30">
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <div className="mt-2 flex items-end justify-between gap-2">
        <p className={`text-3xl font-bold ${complete ? 'text-emerald-600' : 'text-slate-950'}`}>{value}</p>
        <p className="pb-1 text-xs text-slate-400">{helper}</p>
      </div>
    </article>
  );
}

function ParentComplaintCard({ complaint }: { complaint: ParentComplaintSummary }) {
  const status = parentStatusMeta[complaint.status];

  return (
    <Link
      to={`/parent/complaints/${complaint.id}`}
      className="group block rounded-2xl border border-slate-200 p-4 transition hover:border-emerald-200 hover:bg-emerald-50/30 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-emerald-100 sm:p-5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={status.tone}>{status.label}</Badge>
        {complaint.category && <Badge>{CATEGORY_LABEL[complaint.category]}</Badge>}
        <time className="ml-auto text-xs font-medium text-slate-400" dateTime={complaint.createdAt}>
          {dateFormatter.format(new Date(complaint.createdAt))}
        </time>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-bold text-slate-900 transition group-hover:text-emerald-700">
            {complaint.title?.trim() || '제목 없는 민원'}
          </h3>
          <p className="mt-1 line-clamp-1 text-sm text-slate-500">{status.description}</p>
        </div>
        <svg viewBox="0 0 24 24" fill="none" className="size-5 shrink-0 text-slate-300 group-hover:text-emerald-500" aria-hidden="true">
          <path d="m9 5 7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </Link>
  );
}

function ProcessGuide({ number, title, description }: { number: string; title: string; description: string }) {
  return (
    <div className="flex gap-3">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-emerald-700">
        {number}
      </span>
      <div>
        <h3 className="text-sm font-bold text-slate-800">{title}</h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
      </div>
    </div>
  );
}
