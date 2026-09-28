import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  API,
  CATEGORY_LABEL,
  RISK_LABEL,
  STATUS_LABEL,
  type AnswerDraft,
  type AssignComplaintRequest,
  type Complaint,
  type ComplaintDetail,
  type CreateEscalationRequest,
  type Escalation,
  type SimilarCase,
  type TeacherSummary,
} from '@sotong/shared';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';

// 민원 상세 — F1 분류 / F2 위험 / F5 유사 사례 / F4 초안 / F8 이관을 한 화면에서.
export function ComplaintDetailPage() {
  const { id = '' } = useParams();
  const role = useAuthStore((s) => s.user?.role);
  const queryClient = useQueryClient();

  const complaint = useQuery({
    queryKey: ['complaint', id],
    queryFn: async () => {
      const { data } = await api.get<ComplaintDetail>(API.complaints.detail(id));
      return data;
    },
  });

  const similar = useQuery({
    queryKey: ['similar-cases', id],
    queryFn: async () => {
      const { data } = await api.get<SimilarCase[]>(API.complaints.similarCases(id));
      return data;
    },
  });

  const drafts = useQuery({
    queryKey: ['drafts', id],
    queryFn: async () => {
      const { data } = await api.get<AnswerDraft[]>(API.complaints.drafts(id));
      return data;
    },
  });

  const generateDraft = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<AnswerDraft>(API.complaints.draft(id));
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['drafts', id] }),
  });

  if (complaint.isLoading) return <p className="text-sm text-slate-500">불러오는 중...</p>;
  if (complaint.isError || !complaint.data)
    return <p className="text-sm text-red-600">민원을 불러오지 못했습니다.</p>;

  const c = complaint.data;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/inbox" className="text-sm text-slate-400 hover:text-slate-600">
          ← 민원함
        </Link>
        <h1 className="text-xl font-bold mt-2">{c.title ?? '(제목 없음)'}</h1>
        <div className="flex flex-wrap items-center gap-2 mt-2 text-xs">
          <Tag>{RISK_LABEL[c.risk]}</Tag>
          {c.category && <Tag>{CATEGORY_LABEL[c.category]}</Tag>}
          <Tag>{STATUS_LABEL[c.status]}</Tag>
          <span className="text-slate-400">{new Date(c.createdAt).toLocaleString('ko-KR')}</span>
        </div>
      </div>

      {role === 'admin' && <AssigneeSection complaint={c} onDone={() => complaint.refetch()} />}

      <Section title="민원 내용">
        <p className="text-sm whitespace-pre-wrap">{c.body}</p>
      </Section>

      <Section title="AI 분석 (F1 · F2)">
        <dl className="grid sm:grid-cols-2 gap-3 text-sm">
          <Field label="분류">
            {c.classification
              ? `${CATEGORY_LABEL[c.classification.predicted]} (신뢰도 ${c.classification.confidence?.toFixed(2) ?? '-'} · ${c.classification.modelName ?? '-'})`
              : '분석 결과 없음'}
          </Field>
          <Field label="위험도">
            {c.riskAnalysis
              ? `${RISK_LABEL[c.riskAnalysis.risk]} (공격성 ${c.riskAnalysis.aggressionScore ?? '-'})`
              : '분석 결과 없음'}
          </Field>
        </dl>
        {c.riskAnalysis && c.riskAnalysis.reasons.length > 0 && (
          <ul className="mt-3 list-disc pl-5 text-sm text-slate-600">
            {c.riskAnalysis.reasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="유사 사례 (F5)">
        {similar.data && similar.data.length > 0 ? (
          <ul className="space-y-3">
            {similar.data.map((s) => (
              <li key={s.caseId} className="border-l-2 border-slate-200 pl-3">
                <p className="text-sm font-medium">{s.summary}</p>
                <p className="text-sm text-slate-600">대응: {s.resolution}</p>
                <p className="text-xs text-slate-400">유사도 {s.similarity.toFixed(2)}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">
            {similar.isError ? '검색에 실패했습니다.' : '유사한 과거 사례가 없습니다.'}
          </p>
        )}
      </Section>

      <Section title="답변 초안 (F4)">
        <button
          onClick={() => generateDraft.mutate()}
          disabled={generateDraft.isPending}
          className="rounded-md bg-brand text-white px-4 py-2 text-sm font-medium hover:bg-brand-fg disabled:opacity-50"
        >
          {generateDraft.isPending ? '생성 중...' : '초안 생성'}
        </button>
        {generateDraft.isError && (
          <p className="text-sm text-red-600 mt-2">초안 생성에 실패했습니다.</p>
        )}
        <div className="space-y-3 mt-4">
          {drafts.data?.map((d) => (
            <article key={d.id} className="rounded-md bg-slate-50 p-3">
              <p className="text-sm whitespace-pre-wrap">{d.editedBody ?? d.draftBody}</p>
              <p className="text-xs text-slate-400 mt-2">
                {d.modelName} · {new Date(d.createdAt).toLocaleString('ko-KR')}
              </p>
            </article>
          ))}
          {drafts.data?.length === 0 && (
            <p className="text-sm text-slate-500">아직 생성된 초안이 없습니다.</p>
          )}
        </div>
      </Section>

      {(role === 'teacher' || role === 'admin') && (
        <EscalationForm complaintId={id} onDone={() => complaint.refetch()} />
      )}
    </div>
  );
}

// 관리자: 담당 교사 지정·변경. 자동 배정이 담당을 못 찾은 민원(학생 미지정, 반 담당 없음)은
// 이 경로가 아니면 어떤 교사에게도 보이지 않는다.
const REASSIGNABLE = new Set(['received', 'pending_teacher', 'in_progress', 'answered']);

function AssigneeSection({ complaint, onDone }: { complaint: Complaint; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [teacherId, setTeacherId] = useState('');

  const teachers = useQuery({
    queryKey: ['admin-teachers'],
    queryFn: async () => {
      const { data } = await api.get<TeacherSummary[]>(API.admin.teachers);
      return data;
    },
    retry: false,
  });

  const assign = useMutation({
    mutationFn: async (payload: AssignComplaintRequest) => {
      const { data } = await api.patch<Complaint>(API.complaints.assignee(complaint.id), payload);
      return data;
    },
    onSuccess: () => {
      setTeacherId('');
      queryClient.invalidateQueries({ queryKey: ['complaints'] });
      queryClient.invalidateQueries({ queryKey: ['admin-teachers'] });
      onDone();
    },
  });

  // 같은 학교 소속으로 확인된(반을 배정받은) 교사에게만 넘길 수 있다.
  const candidates = (teachers.data ?? []).filter((t) => t.schoolId === complaint.schoolId);
  const current = (teachers.data ?? []).find((t) => t.id === complaint.assignedTeacherId);
  const locked = complaint.filtered || !REASSIGNABLE.has(complaint.status);

  return (
    <Section title="담당 교사">
      <p className="text-sm">
        {complaint.assignedTeacherId ? (
          <>현재 담당: <strong>{current?.name ?? '다른 교사'}</strong></>
        ) : (
          <span className="font-medium text-amber-700">
            담당 교사가 없습니다. 지정하기 전까지 어떤 교사의 민원함에도 나타나지 않습니다.
          </span>
        )}
      </p>
      {locked ? (
        <p className="mt-2 text-xs text-slate-500">
          {complaint.filtered
            ? '차단된 민원은 교사에게 전달하지 않습니다.'
            : '이관·종결된 민원은 담당 교사를 바꿀 수 없습니다.'}
        </p>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (teacherId) assign.mutate({ teacherId });
          }}
          className="mt-3 flex flex-wrap items-center gap-2"
        >
          <select
            value={teacherId}
            onChange={(e) => setTeacherId(e.target.value)}
            className="rounded-md border bg-white px-3 py-2 text-sm"
            aria-label="담당 교사 선택"
          >
            <option value="">교사 선택</option>
            {candidates
              .filter((t) => t.id !== complaint.assignedTeacherId)
              .map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                  {t.assignments.length > 0 ? ` (${t.assignments.map((a) => `${a.grade}-${a.className}`).join(', ')})` : ''}
                </option>
              ))}
          </select>
          <button
            type="submit"
            disabled={!teacherId || assign.isPending}
            className="rounded-md border border-brand px-4 py-2 text-sm font-medium text-brand hover:bg-slate-50 disabled:opacity-50"
          >
            {assign.isPending ? '지정 중...' : '담당 지정'}
          </button>
          {candidates.length === 0 && teachers.isSuccess && (
            <span className="text-xs text-slate-500">
              이 학교 소속 교사가 없습니다. 교사 배정 화면에서 먼저 반을 배정해 주세요.
            </span>
          )}
        </form>
      )}
      {assign.isError && <p className="mt-2 text-sm text-red-600">담당 교사를 지정하지 못했습니다.</p>}
    </Section>
  );
}

// F8: 교사·관리자가 MDT로 이관 요청
function EscalationForm({ complaintId, onDone }: { complaintId: string; onDone: () => void }) {
  const [reason, setReason] = useState('');

  const escalate = useMutation({
    mutationFn: async (payload: CreateEscalationRequest) => {
      const { data } = await api.post<Escalation>(API.escalations.create, payload);
      return data;
    },
    onSuccess: () => {
      setReason('');
      onDone();
    },
  });

  const conflict =
    (escalate.error as { response?: { status?: number } } | null)?.response?.status === 409;

  return (
    <Section title="MDT 이관 (F8)">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          escalate.mutate({ complaintId, reason });
        }}
        className="space-y-3"
      >
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          required
          placeholder="이관 사유를 입력해 주세요 (예: 학교폭력 사안으로 단독 대응 곤란)"
          className="w-full rounded-md border px-3 py-2 text-sm"
        />
        {escalate.isSuccess && (
          <p className="text-sm text-green-600">이관을 요청했습니다.</p>
        )}
        {escalate.isError && (
          <p className="text-sm text-red-600">
            {conflict ? '이미 진행 중인 이관 요청이 있습니다.' : '이관 요청에 실패했습니다.'}
          </p>
        )}
        <button
          type="submit"
          disabled={escalate.isPending}
          className="rounded-md border border-brand text-brand px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
        >
          {escalate.isPending ? '요청 중...' : '이관 요청'}
        </button>
      </form>
    </Section>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border bg-white p-4">
      <h2 className="text-sm font-medium mb-3">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600">{children}</span>;
}
