import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  API,
  type AssignClassRequest,
  type AssignClassResult,
  type TeacherAssignment,
  type TeacherSummary,
} from '@sotong/shared';
import { api } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { LoadingCards } from '@/components/ui/LoadingCards';
import { PageHeader } from '@/components/ui/PageHeader';

function httpStatus(error: unknown): number | undefined {
  return (error as { response?: { status?: number } })?.response?.status;
}

function assignmentLabel(a: TeacherAssignment): string {
  const cls = a.grade != null && a.className ? `${a.grade}학년 ${a.className}반` : '반 미지정';
  return a.studentId ? `${cls} (학생 개별)` : cls;
}

// 관리자 — 교사에게 담당 학년·반을 배정한다.
// 교사 민원함은 배정된 반의 민원만 보여주므로, 가입만 한 교사는 여기서 배정받기 전까지
// 민원이 0건이다. 배정은 곧 그 반 민원 열람 권한이라 관리자만 할 수 있다.
export function TeacherAssignmentsPage() {
  // 결과 안내는 페이지에 둔다. 배정하면 교사가 '배정 대기'에서 '담당 중'으로 옮겨가며
  // 행 컴포넌트가 새로 그려지므로, 행 안에 두면 안내가 뜨자마자 사라진다.
  const [notice, setNotice] = useState<string | null>(null);
  const teachers = useQuery({
    queryKey: ['admin-teachers'],
    queryFn: async () => {
      const { data } = await api.get<TeacherSummary[]>(API.admin.teachers);
      return data;
    },
    retry: false,
  });

  const items = teachers.data ?? [];
  const waiting = items.filter((t) => t.assignments.length === 0);
  const assigned = items.filter((t) => t.assignments.length > 0);

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Admin workspace"
        title="교사 배정"
        description="교사에게 담당 학년·반을 맡기면 그 반 학부모 민원이 해당 교사의 민원함으로 전달됩니다."
      />

      {notice && (
        <div role="status" className="flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(null)} className="shrink-0 text-xs font-semibold text-emerald-700 hover:text-emerald-900">
            닫기
          </button>
        </div>
      )}

      {teachers.isLoading && <LoadingCards count={2} />}

      {teachers.isError && (
        <EmptyState
          title="교사 목록을 불러오지 못했습니다"
          description={
            httpStatus(teachers.error) === 409
              ? '관리자 계정에 소속 학교가 없어 교사를 배정할 수 없습니다. 운영 담당자에게 학교 연결을 요청해 주세요.'
              : '백엔드 연결 상태를 확인한 뒤 다시 시도해 주세요.'
          }
        />
      )}

      {teachers.isSuccess && items.length === 0 && (
        <EmptyState
          title="아직 가입한 교사가 없습니다"
          description="교사가 회원가입하면 이곳에 나타나고, 담당 반을 배정할 수 있습니다."
        />
      )}

      {waiting.length > 0 && (
        <TeacherSection
          title="배정 대기"
          description="담당 반이 없어 민원을 받지 못하는 교사입니다."
          teachers={waiting}
          onNotice={setNotice}
          highlight
        />
      )}

      {assigned.length > 0 && (
        <TeacherSection
          title="담당 중"
          description="같은 반을 다른 교사에게 배정하면 기존 담당은 해제됩니다."
          teachers={assigned}
          onNotice={setNotice}
        />
      )}
    </div>
  );
}

function TeacherSection({
  title,
  description,
  teachers,
  onNotice,
  highlight = false,
}: {
  title: string;
  description: string;
  teachers: TeacherSummary[];
  onNotice: (message: string) => void;
  highlight?: boolean;
}) {
  return (
    <section
      className={`overflow-hidden rounded-2xl border bg-white shadow-sm shadow-slate-200/40 ${
        highlight ? 'border-amber-200' : 'border-slate-200'
      }`}
    >
      <div className={`border-b px-5 py-4 ${highlight ? 'border-amber-100 bg-amber-50/60' : 'border-slate-100'}`}>
        <h2 className="font-bold text-slate-950">
          {title} <span className="text-slate-400">{teachers.length}</span>
        </h2>
        <p className="mt-0.5 text-xs text-slate-500">{description}</p>
      </div>
      <ul className="divide-y divide-slate-100">
        {teachers.map((t) => (
          <TeacherRow key={t.id} teacher={t} onNotice={onNotice} />
        ))}
      </ul>
    </section>
  );
}

function TeacherRow({ teacher, onNotice }: { teacher: TeacherSummary; onNotice: (message: string) => void }) {
  const queryClient = useQueryClient();
  const [grade, setGrade] = useState('');
  const [className, setClassName] = useState('');
  const [transferOpen, setTransferOpen] = useState(true);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['admin-teachers'] });
    queryClient.invalidateQueries({ queryKey: ['complaints'] });
  };

  const assign = useMutation({
    mutationFn: async (payload: AssignClassRequest) => {
      const { data } = await api.post<AssignClassResult>(API.admin.assignments, payload);
      return data;
    },
    onSuccess: (result) => {
      const parts = [`${teacher.name} 선생님께 ${assignmentLabel(result.assignment)}을 배정했습니다.`];
      if (result.replaced > 0) parts.push(`기존 담당 배정 ${result.replaced}건을 해제했습니다.`);
      if (result.movedComplaints > 0) parts.push(`진행 중 민원 ${result.movedComplaints}건을 옮겼습니다.`);
      onNotice(parts.join(' '));
      setGrade('');
      setClassName('');
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: async (assignmentId: string) => {
      await api.delete(API.admin.assignment(assignmentId));
    },
    onSuccess: () => {
      onNotice('배정을 해제했습니다. 이미 받은 민원은 그대로 남고, 새 민원은 더 이상 전달되지 않습니다.');
      refresh();
    },
  });

  const gradeNumber = Number(grade);
  const canSubmit = Number.isInteger(gradeNumber) && gradeNumber >= 1 && gradeNumber <= 12 && className.trim() !== '';

  return (
    <li className="p-4 sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="font-bold text-slate-900">{teacher.name}</p>
          <p className="truncate text-sm text-slate-500">{teacher.email ?? '이메일 없음'}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {teacher.assignments.length === 0 ? (
              <Badge tone="warning">담당 반 없음</Badge>
            ) : (
              teacher.assignments.map((a) => (
                <span
                  key={a.id}
                  className="inline-flex items-center gap-1 rounded-full bg-indigo-50 py-1 pl-2.5 pr-1 text-xs font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-100"
                >
                  {assignmentLabel(a)}
                  <button
                    type="button"
                    onClick={() => remove.mutate(a.id)}
                    disabled={remove.isPending}
                    className="flex size-5 items-center justify-center rounded-full text-indigo-400 transition hover:bg-indigo-100 hover:text-indigo-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-300 disabled:opacity-50"
                    aria-label={`${assignmentLabel(a)} 배정 해제`}
                  >
                    <svg viewBox="0 0 24 24" fill="none" className="size-3" aria-hidden="true">
                      <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
                    </svg>
                  </button>
                </span>
              ))
            )}
            {teacher.openComplaints > 0 && (
              <span className="text-xs text-slate-500">진행 중 민원 {teacher.openComplaints}건</span>
            )}
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!canSubmit) return;
            assign.mutate({ teacherId: teacher.id, grade: gradeNumber, className: className.trim(), transferOpen });
          }}
          className="flex flex-wrap items-end gap-2"
        >
          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-slate-500">학년</span>
            <input
              type="number"
              inputMode="numeric"
              min={1}
              max={12}
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
              placeholder="3"
              className="h-10 w-20 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm outline-none transition focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-50"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-semibold text-slate-500">반</span>
            <input
              value={className}
              onChange={(e) => setClassName(e.target.value)}
              placeholder="2"
              maxLength={50}
              className="h-10 w-24 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm outline-none transition focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-50"
            />
          </label>
          <label className="flex h-10 items-center gap-2 px-1 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={transferOpen}
              onChange={(e) => setTransferOpen(e.target.checked)}
              className="size-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            />
            진행 중 민원도 옮기기
          </label>
          <button
            type="submit"
            disabled={!canSubmit || assign.isPending}
            className="h-10 rounded-lg bg-indigo-600 px-4 text-sm font-bold text-white transition hover:bg-indigo-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-indigo-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {assign.isPending ? '배정 중...' : '배정'}
          </button>
        </form>
      </div>

      {(assign.isError || remove.isError) && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {httpStatus(assign.error ?? remove.error) === 404
            ? '이 교사는 다른 학교 소속이거나 배정할 수 없는 계정입니다.'
            : '처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'}
        </p>
      )}
    </li>
  );
}
