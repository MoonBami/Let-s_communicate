import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { API, type GuestComplaintView } from '@sotong/shared';
import { api } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { parentStatusMeta } from '@/components/parent/complaintStatus';

function httpStatus(error: unknown): number | undefined {
  return (error as { response?: { status?: number } })?.response?.status;
}

const dateFormat = new Intl.DateTimeFormat('ko-KR', {
  month: 'long',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
});

// 비회원 민원 조회 — 접수번호 + 숫자 4자리 비밀번호.
// 로그인 없이 접수한 학부모가 처리 상태와 선생님 답변을 확인하는 유일한 경로다.
// 알림이 없으므로 학부모가 직접 들어와 확인한다(설계 결정). 회신 기능은 두지 않는다.
export function GuestLookupPage() {
  const [code, setCode] = useState('');
  const [pin, setPin] = useState('');

  const lookup = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<GuestComplaintView>(API.complaints.lookup, {
        receiptCode: code.trim(),
        pin,
      });
      return data;
    },
  });

  const canSubmit = code.trim().length >= 8 && /^\d{4}$/.test(pin);
  const status = httpStatus(lookup.error);

  return (
    <div className="mx-auto min-h-screen max-w-2xl px-4 py-10">
      <Link
        to="/login"
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 transition hover:text-emerald-700"
      >
        <svg viewBox="0 0 24 24" fill="none" className="size-4" aria-hidden="true">
          <path d="m15 5-7 7 7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        처음으로
      </Link>

      <header className="mt-5">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-emerald-600">My complaint</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">내 민원 확인</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          접수할 때 받은 접수번호와 직접 정한 비밀번호 4자리를 입력해 주세요.
        </p>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) lookup.mutate();
        }}
        className="mt-7 space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/50 sm:p-7"
      >
        <div className="grid gap-4 sm:grid-cols-[1fr_10rem]">
          <label className="block space-y-2">
            <span className="text-sm font-bold text-slate-700">접수번호</span>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="ABCD-2345"
              autoComplete="off"
              maxLength={12}
              className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 font-mono text-base tracking-widest outline-none transition placeholder:text-slate-300 focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-50"
            />
          </label>
          <label className="block space-y-2">
            <span className="text-sm font-bold text-slate-700">비밀번호</span>
            <input
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
              type="password"
              inputMode="numeric"
              autoComplete="off"
              placeholder="숫자 4자리"
              className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-center font-mono text-base tracking-[0.5em] outline-none transition placeholder:tracking-normal placeholder:text-slate-400 focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-50"
            />
          </label>
        </div>

        {lookup.isError && (
          <div role="alert" className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
            {status === 404
              ? '접수번호 또는 비밀번호가 올바르지 않습니다.'
              : status === 429
                ? '여러 번 틀려 잠시 조회가 제한되었습니다. 10분쯤 뒤에 다시 시도해 주세요.'
                : '조회하지 못했습니다. 잠시 후 다시 시도해 주세요.'}
          </div>
        )}

        <button
          type="submit"
          disabled={!canSubmit || lookup.isPending}
          className="h-12 w-full rounded-xl bg-emerald-600 text-sm font-bold text-white transition hover:bg-emerald-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {lookup.isPending ? '확인 중...' : '확인하기'}
        </button>
        <p className="text-center text-xs text-slate-400">
          접수번호나 비밀번호를 잊으셨다면 다시 찾을 수 없습니다. 새로 접수해 주세요.
        </p>
      </form>

      {lookup.data && <ComplaintResult view={lookup.data} />}
    </div>
  );
}

function ComplaintResult({ view }: { view: GuestComplaintView }) {
  // 자동 응대는 아직 실제 안내를 보내지 않는다. 답변이 없는데 '안내 완료'로 보이면
  // 학부모는 답을 받은 줄 알고 기다리지 않는다 — 답변이 오기 전까지는 확인 중으로 보인다.
  const shownStatus =
    view.status === 'auto_answered' && view.answers.length === 0 ? 'pending_teacher' : view.status;
  const meta = parentStatusMeta[shownStatus];

  return (
    <section className="mt-6 space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/50 sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          <span className="font-mono text-xs text-slate-400">{view.receiptCode}</span>
        </div>
        <h2 className="mt-3 text-lg font-bold text-slate-950">{view.title || '제목 없음'}</h2>
        <p className="mt-1 text-xs text-slate-400">{dateFormat.format(new Date(view.createdAt))} 접수</p>
        <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-700">{view.body}</p>
        <p className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">{meta.description}</p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/50 sm:p-7">
        <h3 className="font-bold text-slate-950">받은 답변</h3>
        {view.answers.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">
            아직 답변이 없습니다. 선생님이 확인 후 답변을 남기면 이곳에 표시됩니다.
          </p>
        ) : (
          <ol className="mt-4 space-y-3">
            {view.answers.map((a, i) => (
              <li key={i} className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-4">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-bold text-emerald-800">{a.senderLabel}</span>
                  <span className="text-slate-400">{dateFormat.format(new Date(a.createdAt))}</span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">{a.body}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
