import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  API,
  CATEGORY_LABEL,
  COMPLAINT_CATEGORY,
  RISK_LABEL,
  STATUS_LABEL,
  type Complaint,
  type ComplaintCategory,
  type ComplaintStatus,
  type Paginated,
  type RiskLevel,
} from '@sotong/shared';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { LoadingCards } from '@/components/ui/LoadingCards';
import { PageHeader } from '@/components/ui/PageHeader';

type CategoryFilter = ComplaintCategory | 'all';
type StatusFilter = ComplaintStatus | 'all';
type SortOption = 'newest' | 'risk';

const riskOrder: Record<RiskLevel, number> = {
  low: 0,
  medium: 1,
  high: 2,
  critical: 3,
};

const riskTone: Record<RiskLevel, BadgeTone> = {
  low: 'neutral',
  medium: 'warning',
  high: 'warning',
  critical: 'danger',
};

const statusTone: Partial<Record<ComplaintStatus, BadgeTone>> = {
  pending_teacher: 'brand',
  in_progress: 'warning',
  answered: 'success',
  escalated: 'danger',
  closed: 'neutral',
};

const dateTimeFormatter = new Intl.DateTimeFormat('ko-KR', {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

// 교사 민원함 — 필터를 통과한 민원을 한눈에 분류하고 우선순위를 판단한다.
export function TeacherInboxPage() {
  const role = useAuthStore((state) => state.user?.role);
  const [searchTerm, setSearchTerm] = useState('');
  const [category, setCategory] = useState<CategoryFilter>('all');
  const [status, setStatus] = useState<StatusFilter>('all');
  const [sort, setSort] = useState<SortOption>('newest');

  const complaints = useQuery({
    queryKey: ['complaints'],
    queryFn: async () => {
      const { data } = await api.get<Paginated<Complaint>>(API.complaints.list);
      return data;
    },
  });

  const items = complaints.data?.items ?? [];
  const filteredItems = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLocaleLowerCase('ko-KR');

    return items
      .filter((complaint) => {
        const matchesSearch =
          normalizedSearch.length === 0 ||
          complaint.title?.toLocaleLowerCase('ko-KR').includes(normalizedSearch) ||
          complaint.body.toLocaleLowerCase('ko-KR').includes(normalizedSearch);
        const matchesCategory = category === 'all' || complaint.category === category;
        const matchesStatus = status === 'all' || complaint.status === status;

        return matchesSearch && matchesCategory && matchesStatus;
      })
      .sort((a, b) => {
        if (sort === 'risk') {
          const riskDifference = riskOrder[b.risk] - riskOrder[a.risk];
          if (riskDifference !== 0) return riskDifference;
        }
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      });
  }, [category, items, searchTerm, sort, status]);

  const hasActiveFilters = searchTerm.trim() !== '' || category !== 'all' || status !== 'all';
  const pendingCount = items.filter((item) =>
    ['pending_teacher', 'in_progress'].includes(item.status),
  ).length;
  const highRiskCount = items.filter((item) => ['high', 'critical'].includes(item.risk)).length;
  const escalatedCount = items.filter((item) => item.status === 'escalated').length;
  const pageCopy =
    role === 'admin'
      ? {
          eyebrow: 'Admin workspace',
          title: '전체 민원',
          description: '학교에 접수된 민원의 분류와 처리 상태를 전체적으로 확인하세요.',
        }
      : role === 'mdt'
        ? {
            eyebrow: 'MDT workspace',
            title: '검토 민원',
            description: '전문 대응이 필요한 민원과 현재 처리 상태를 확인하세요.',
          }
        : {
            eyebrow: 'Teacher workspace',
            title: '민원함',
            description: '배정된 민원의 위험도와 처리 상태를 확인하고 우선순위에 따라 대응하세요.',
          };

  function resetFilters() {
    setSearchTerm('');
    setCategory('all');
    setStatus('all');
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow={pageCopy.eyebrow}
        title={pageCopy.title}
        description={pageCopy.description}
        action={
          <div className="inline-flex items-center gap-2 self-start rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-100">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            실시간 업데이트
          </div>
        }
      />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="민원 현황 요약">
        <SummaryCard label="전체 민원" value={complaints.data?.total ?? items.length} helper="누적 배정 건" tone="brand" />
        <SummaryCard label="확인 필요" value={pendingCount} helper="현재 목록 기준" tone="warning" />
        <SummaryCard label="높은 위험" value={highRiskCount} helper="높음·긴급" tone="danger" />
        <SummaryCard label="MDT 이관" value={escalatedCount} helper="현재 목록 기준" tone="neutral" />
      </section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40">
        <div className="border-b border-slate-100 p-4 sm:p-5">
          <div className="grid gap-3 lg:grid-cols-[minmax(240px,1fr)_180px_180px_150px]">
            <label className="relative block">
              <span className="sr-only">민원 검색</span>
              <svg
                viewBox="0 0 24 24"
                fill="none"
                className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400"
                aria-hidden="true"
              >
                <circle cx="11" cy="11" r="6" stroke="currentColor" strokeWidth="1.8" />
                <path d="m16 16 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
              <input
                type="search"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="제목이나 내용 검색"
                className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-50"
              />
            </label>

            <FilterSelect
              label="카테고리"
              value={category}
              onChange={(value) => setCategory(value as CategoryFilter)}
            >
              <option value="all">전체 카테고리</option>
              {COMPLAINT_CATEGORY.map((value) => (
                <option key={value} value={value}>
                  {CATEGORY_LABEL[value]}
                </option>
              ))}
            </FilterSelect>

            <FilterSelect
              label="처리 상태"
              value={status}
              onChange={(value) => setStatus(value as StatusFilter)}
            >
              <option value="all">전체 상태</option>
              <option value="pending_teacher">교사 확인 대기</option>
              <option value="in_progress">처리 중</option>
              <option value="answered">답변 완료</option>
              <option value="escalated">MDT 이관</option>
              <option value="closed">종료</option>
            </FilterSelect>

            <FilterSelect
              label="정렬"
              value={sort}
              onChange={(value) => setSort(value as SortOption)}
            >
              <option value="newest">최신순</option>
              <option value="risk">위험도순</option>
            </FilterSelect>
          </div>
        </div>

        <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/70 px-4 py-3 sm:px-5">
          <p className="text-sm font-semibold text-slate-700">
            민원 <span className="text-blue-600">{filteredItems.length}</span>건
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="text-xs font-semibold text-slate-500 transition hover:text-blue-600"
            >
              필터 초기화
            </button>
          )}
        </div>

        <div className="p-4 sm:p-5">
          {complaints.isLoading && <LoadingCards />}

          {complaints.isError && (
            <EmptyState
              title="민원 목록을 불러오지 못했습니다"
              description="백엔드 연결 상태를 확인한 뒤 다시 시도해 주세요."
              action={
                <button
                  type="button"
                  onClick={() => complaints.refetch()}
                  disabled={complaints.isFetching}
                  className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
                >
                  {complaints.isFetching ? '다시 불러오는 중...' : '다시 시도'}
                </button>
              }
            />
          )}

          {complaints.isSuccess && filteredItems.length > 0 && (
            <div className="space-y-3">
              {filteredItems.map((complaint) => (
                <ComplaintCard key={complaint.id} complaint={complaint} />
              ))}
            </div>
          )}

          {complaints.isSuccess && filteredItems.length === 0 && (
            <EmptyState
              title={hasActiveFilters ? '검색 조건에 맞는 민원이 없습니다' : '배정된 민원이 없습니다'}
              description={
                hasActiveFilters
                  ? '검색어나 필터 조건을 변경해서 다시 확인해 보세요.'
                  : '새로운 민원이 배정되면 이곳에서 확인할 수 있습니다.'
              }
              action={
                hasActiveFilters ? (
                  <button
                    type="button"
                    onClick={resetFilters}
                    className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-blue-200 hover:text-blue-600"
                  >
                    필터 초기화
                  </button>
                ) : undefined
              }
            />
          )}
        </div>
      </section>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  helper,
  tone,
}: {
  label: string;
  value: number;
  helper: string;
  tone: BadgeTone;
}) {
  const accentClasses: Record<BadgeTone, string> = {
    neutral: 'bg-slate-500',
    brand: 'bg-blue-600',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger: 'bg-red-500',
  };

  return (
    <article className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/30">
      <span className={`absolute inset-y-0 left-0 w-1 ${accentClasses[tone]}`} />
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <div className="mt-2 flex items-end justify-between gap-3">
        <p className="text-3xl font-bold tracking-tight text-slate-950">{value}</p>
        <p className="pb-1 text-xs text-slate-400">{helper}</p>
      </div>
    </article>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label>
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-medium text-slate-700 outline-none transition focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-50"
      >
        {children}
      </select>
    </label>
  );
}

function ComplaintCard({ complaint }: { complaint: Complaint }) {
  const title = complaint.title?.trim() || '제목 없는 민원';

  return (
    <Link
      to={`/complaints/${complaint.id}`}
      className="group block rounded-2xl border border-slate-200 bg-white p-4 transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-lg hover:shadow-blue-100/50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-100 sm:p-5"
    >
      <div className="flex items-start gap-4">
        <span
          className={`mt-1 hidden h-12 w-1 shrink-0 rounded-full sm:block ${
            complaint.risk === 'critical'
              ? 'bg-red-500'
              : complaint.risk === 'high'
                ? 'bg-orange-500'
                : complaint.risk === 'medium'
                  ? 'bg-amber-400'
                  : 'bg-slate-200'
          }`}
        />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={riskTone[complaint.risk]}>위험도 {RISK_LABEL[complaint.risk]}</Badge>
            {complaint.category && <Badge tone="brand">{CATEGORY_LABEL[complaint.category]}</Badge>}
            <Badge tone={statusTone[complaint.status] ?? 'neutral'}>{STATUS_LABEL[complaint.status]}</Badge>
            <time dateTime={complaint.createdAt} className="ml-auto text-xs font-medium text-slate-400">
              {dateTimeFormatter.format(new Date(complaint.createdAt))}
            </time>
          </div>

          <div className="mt-3 flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-base font-bold text-slate-900 transition group-hover:text-blue-700">
                {title}
              </h2>
              <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">{complaint.body}</p>
            </div>
            <span className="hidden size-9 shrink-0 items-center justify-center rounded-full bg-slate-50 text-slate-400 transition group-hover:bg-blue-50 group-hover:text-blue-600 sm:flex">
              <svg viewBox="0 0 24 24" fill="none" className="size-4" aria-hidden="true">
                <path d="m9 5 7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}
