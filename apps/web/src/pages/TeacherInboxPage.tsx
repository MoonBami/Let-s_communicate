import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  API,
  CATEGORY_LABEL,
  RISK_LABEL,
  STATUS_LABEL,
  type Complaint,
  type Paginated,
} from '@sotong/shared';
import { api } from '@/lib/api';

const riskColor: Record<string, string> = {
  low: 'bg-slate-100 text-slate-600',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

// 교사 민원함 — 필터를 통과한 '정당한 민원'만 노출.
export function TeacherInboxPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['complaints'],
    queryFn: async () => {
      const { data } = await api.get<Paginated<Complaint>>(API.complaints.list);
      return data;
    },
  });

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">민원함</h1>

      {isLoading && <p className="text-sm text-slate-500">불러오는 중...</p>}
      {isError && (
        <p className="text-sm text-slate-500">
          목록을 불러오지 못했습니다. (백엔드 연동 후 표시됩니다)
        </p>
      )}

      <div className="space-y-2">
        {data?.items.map((c) => (
          <Link
            key={c.id}
            to={`/complaints/${c.id}`}
            className="block rounded-lg border bg-white p-4 hover:border-brand"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs px-2 py-0.5 rounded ${riskColor[c.risk] ?? ''}`}>
                {RISK_LABEL[c.risk]}
              </span>
              {c.category && (
                <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                  {CATEGORY_LABEL[c.category]}
                </span>
              )}
              <span className="text-xs text-slate-400 ml-auto">{STATUS_LABEL[c.status]}</span>
            </div>
            <h2 className="font-medium">{c.title ?? '(제목 없음)'}</h2>
            <p className="text-sm text-slate-600 line-clamp-2">{c.body}</p>
          </Link>
        ))}
        {data && data.items.length === 0 && (
          <p className="text-sm text-slate-500">표시할 민원이 없습니다.</p>
        )}
      </div>
    </div>
  );
}
