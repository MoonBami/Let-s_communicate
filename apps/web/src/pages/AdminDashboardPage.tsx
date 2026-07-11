import { useQuery } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { API, CATEGORY_LABEL, type ComplaintStat } from '@sotong/shared';
import { api } from '@/lib/api';

// F9 관리자 통계 대시보드
export function AdminDashboardPage() {
  const { data, isError } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      const { data } = await api.get<ComplaintStat[]>(API.dashboard.stats);
      return data;
    },
  });

  // 카테고리별 집계 (백엔드 미연동 시 데모 데이터)
  const rows = data ?? DEMO_STATS;
  const byCategory = aggregateByCategory(rows);

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">관리자 대시보드</h1>
      {isError && (
        <p className="text-sm text-slate-500 mb-2">※ 백엔드 미연동 상태 — 데모 데이터 표시 중</p>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard label="총 민원" value={sum(rows)} />
        <StatCard label="긴급/높음" value={countRisk(rows, ['high', 'critical'])} />
        <StatCard label="자동 응대" value={countStatus(rows, 'auto_answered')} />
        <StatCard label="이관" value={countStatus(rows, 'escalated')} />
      </div>

      <div className="rounded-lg border bg-white p-4">
        <h2 className="text-sm font-medium mb-3">카테고리별 민원 수</h2>
        <div style={{ width: '100%', height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={byCategory}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" fontSize={12} />
              <YAxis fontSize={12} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="total" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

// --- 집계 헬퍼 ---
const sum = (rows: ComplaintStat[]) => rows.reduce((a, r) => a + r.total, 0);
const countRisk = (rows: ComplaintStat[], risks: string[]) =>
  rows.filter((r) => risks.includes(r.risk)).reduce((a, r) => a + r.total, 0);
const countStatus = (rows: ComplaintStat[], status: string) =>
  rows.filter((r) => r.status === status).reduce((a, r) => a + r.total, 0);

function aggregateByCategory(rows: ComplaintStat[]) {
  const map = new Map<string, number>();
  for (const r of rows) {
    const label = r.category ? CATEGORY_LABEL[r.category] : '기타';
    map.set(label, (map.get(label) ?? 0) + r.total);
  }
  return [...map.entries()].map(([label, total]) => ({ label, total }));
}

const DEMO_STATS: ComplaintStat[] = [
  { category: 'administrative', risk: 'low', status: 'auto_answered', day: '2026-07-11', total: 42 },
  { category: 'learning', risk: 'medium', status: 'answered', day: '2026-07-11', total: 18 },
  { category: 'grades', risk: 'medium', status: 'in_progress', day: '2026-07-11', total: 9 },
  { category: 'violence_dispute', risk: 'high', status: 'escalated', day: '2026-07-11', total: 4 },
  { category: 'life', risk: 'low', status: 'answered', day: '2026-07-11', total: 12 },
];
