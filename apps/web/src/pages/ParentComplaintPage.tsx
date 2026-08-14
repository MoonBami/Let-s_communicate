import { useForm } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { API, type CreateComplaintRequest, type Complaint } from '@sotong/shared';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';

// 데모 시드(seed.py)와 맞춘 고정 UUID. 학교·학생 선택 API가 준비되면 제거한다.
const DEMO_SCHOOL_ID = '11111111-1111-1111-1111-111111111111';
const DEMO_STUDENT_ID = '22222222-2222-2222-2222-222222222222';

// 학부모 민원 접수 화면. 공개 접수와 로그인 학부모 작업공간에서 함께 사용한다.
export function ParentComplaintPage() {
  const user = useAuthStore((state) => state.user);
  const isParentWorkspace = user?.role === 'parent';
  const queryClient = useQueryClient();
  const { register, handleSubmit, reset, formState } = useForm<CreateComplaintRequest>();

  const mutation = useMutation({
    mutationFn: async (payload: CreateComplaintRequest) => {
      const { data } = await api.post<Complaint>(API.complaints.create, {
        ...payload,
        schoolId: DEMO_SCHOOL_ID,
        studentId: DEMO_STUDENT_ID,
      });
      return data;
    },
    onSuccess: (complaint) => {
      // 차단된 민원은 폼을 비우지 않는다. 작성한 내용을 지워버리면 학부모가
      // 처음부터 다시 써야 하고, 그럴 바엔 포기하거나 더 격앙된 채로 다시
      // 제출하게 된다. 표현만 고쳐 다시 낼 수 있게 남겨둔다.
      if (complaint.status === 'filtered_blocked') return;
      reset();
      queryClient.invalidateQueries({ queryKey: ['parent-complaints'] });
    },
  });

  return (
    <div className={isParentWorkspace ? 'mx-auto max-w-3xl' : 'mx-auto min-h-screen max-w-3xl px-4 py-10'}>
      <Link
        to={isParentWorkspace ? '/parent' : '/login'}
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 transition hover:text-emerald-700"
      >
        <svg viewBox="0 0 24 24" fill="none" className="size-4" aria-hidden="true">
          <path d="m15 5-7 7 7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {isParentWorkspace ? '내 민원으로' : '로그인으로'}
      </Link>

      <header className="mt-5">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-emerald-600">New complaint</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">새 민원 접수</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          정확한 확인을 위해 사실 중심으로 작성해 주세요. 접수된 내용은 분류·검토 후 담당자에게 안전하게 전달됩니다.
        </p>
      </header>

      {mutation.isSuccess && mutation.data ? (
        // 접수 결과를 상태별로 다르게 알린다. 차단된 민원까지 "접수되었습니다"로
        // 보여주면 학부모는 전달된 줄 알고 답을 기다리다 같은 민원을 또 넣는다.
        mutation.data.status === 'filtered_blocked' ? (
          <BlockedNotice onRevise={() => mutation.reset()} />
        ) : (
          <SuccessReceipt complaint={mutation.data} isParentWorkspace={isParentWorkspace} onWriteAnother={() => mutation.reset()} />
        )
      ) : (
        <form
          onSubmit={handleSubmit((values) => mutation.mutate(values))}
          className="mt-7 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm shadow-slate-200/40"
        >
          <div className="space-y-6 p-5 sm:p-7">
            <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3">
              <p className="text-sm font-semibold text-emerald-900">작성 전에 확인해 주세요</p>
              <p className="mt-1 text-xs leading-5 text-emerald-800">
                학생의 안전과 관련된 긴급 상황은 이 민원 창구의 답변을 기다리지 말고 학교나 관계 기관에 즉시 연락해 주세요.
              </p>
            </div>

            <label className="block space-y-2">
              <span className="text-sm font-bold text-slate-700">제목</span>
              <input
                {...register('title', { maxLength: 120 })}
                className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm outline-none transition placeholder:text-slate-400 focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-50"
                placeholder="예: 급식 알레르기 관련 문의드립니다"
                maxLength={120}
              />
              <span className="text-xs text-slate-400">핵심 내용을 짧게 적어 주세요.</span>
            </label>

            <label className="block space-y-2">
              <span className="text-sm font-bold text-slate-700">
                내용 <span className="text-emerald-600">*</span>
              </span>
              <textarea
                {...register('body', { required: true, minLength: 10 })}
                rows={9}
                className="w-full resize-y rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 outline-none transition placeholder:text-slate-400 focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-50"
                placeholder="언제, 어디서, 어떤 일이 있었는지 구체적으로 작성해 주세요."
              />
              {formState.errors.body ? (
                <span className="text-xs font-medium text-red-600">내용을 10자 이상 입력해 주세요.</span>
              ) : (
                <span className="text-xs text-slate-400">개인 연락처와 불필요한 민감정보는 작성하지 마세요.</span>
              )}
            </label>

            <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-4">
              <input
                type="checkbox"
                required
                className="mt-0.5 size-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
              />
              <span className="text-xs leading-5 text-slate-600">
                민원 처리를 위해 작성한 내용을 학교 담당자에게 전달하는 것에 동의합니다.
              </span>
            </label>

            {mutation.isError && (
              <div role="alert" className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
                접수하지 못했습니다. 잠시 후 다시 시도해 주세요.
              </div>
            )}
          </div>

          <div className="flex flex-col-reverse gap-3 border-t border-slate-100 bg-slate-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-7">
            <p className="text-xs text-slate-400">접수 후에는 처리 단계에 따라 담당자가 내용을 확인합니다.</p>
            <button
              type="submit"
              disabled={mutation.isPending || formState.isSubmitting}
              className="inline-flex min-w-32 items-center justify-center rounded-xl bg-emerald-600 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mutation.isPending ? '안전하게 접수 중...' : '민원 접수하기'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

/** 욕설·위협 필터(F3)에 걸려 전달되지 않은 경우.
 *
 * 어떤 표현이 걸렸는지는 알려주지 않는다 — 구체적으로 알려주면 필터를 우회하는
 * 방법을 가르쳐주는 셈이 된다. 대신 무엇을 해야 하는지는 분명히 안내한다.
 * 작성한 내용은 폼에 그대로 남아 있으므로 표현만 고쳐 다시 낼 수 있다.
 */
function BlockedNotice({ onRevise }: { onRevise: () => void }) {
  return (
    <section
      role="alert"
      className="mt-7 rounded-2xl border border-amber-200 bg-white p-6 shadow-lg shadow-amber-100/50 sm:p-9"
    >
      <span className="flex size-14 items-center justify-center rounded-full bg-amber-100 text-amber-700">
        <svg viewBox="0 0 24 24" fill="none" className="size-7" aria-hidden="true">
          <path d="M12 9v4m0 3.5v.5M10.3 4.3 2.8 17.5A1.5 1.5 0 0 0 4.1 20h15.8a1.5 1.5 0 0 0 1.3-2.5L13.7 4.3a2 2 0 0 0-3.4 0Z"
            stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>

      <h2 className="mt-4 text-xl font-bold text-slate-950">담당자에게 전달되지 않았습니다</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        작성하신 내용에 <strong className="font-bold">담당자에게 전달할 수 없는 표현</strong>이 포함되어 있어
        접수가 보류되었습니다. 표현을 다듬어 다시 제출해 주세요.
      </p>

      <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
        <p className="text-sm font-semibold text-slate-700">이렇게 바꿔 보세요</p>
        <ul className="mt-2 space-y-1.5 text-xs leading-5 text-slate-600">
          <li>· 감정을 표현하는 말보다 <strong>언제·어디서·무슨 일이 있었는지</strong> 사실을 적어 주세요.</li>
          <li>· 상대를 향한 비난이나 위협하는 표현은 빼 주세요. 그래도 문제는 그대로 전달됩니다.</li>
          <li>· 원하는 조치가 무엇인지 구체적으로 적으면 처리가 빨라집니다.</li>
        </ul>
      </div>

      <p className="mt-4 text-xs leading-5 text-slate-500">
        작성하신 내용은 학교 관리자가 확인할 수 있도록 보관됩니다. 학생의 안전과 관련된 긴급한 상황이라면
        이 창구의 답변을 기다리지 말고 학교나 관계 기관에 바로 연락해 주세요.
      </p>

      <div className="mt-6">
        <button
          type="button"
          onClick={onRevise}
          className="w-full rounded-xl bg-amber-600 px-5 py-3 text-sm font-bold text-white transition hover:bg-amber-700 sm:w-auto"
        >
          내용 수정하기
        </button>
      </div>
    </section>
  );
}

function SuccessReceipt({
  complaint,
  isParentWorkspace,
  onWriteAnother,
}: {
  complaint: Complaint;
  isParentWorkspace: boolean;
  onWriteAnother: () => void;
}) {
  return (
    <section className="mt-7 rounded-2xl border border-emerald-100 bg-white p-6 text-center shadow-lg shadow-emerald-100/50 sm:p-9">
      <span className="mx-auto flex size-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
        <svg viewBox="0 0 24 24" fill="none" className="size-7" aria-hidden="true">
          <path d="m6 12 4 4 8-9" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <h2 className="mt-4 text-xl font-bold text-slate-950">민원이 접수되었습니다</h2>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        {complaint.status === 'pending_teacher'
          ? '담당 선생님께 전달되었습니다. 확인 후 처리 단계가 업데이트됩니다.'
          : '접수 내용을 분류했습니다. 처리 단계는 접수번호로 확인할 수 있습니다.'}
      </p>

      <div className="mx-auto mt-5 max-w-sm rounded-xl bg-slate-50 px-4 py-3 text-left">
        <p className="text-xs font-medium text-slate-400">접수번호</p>
        <p className="mt-1 break-all font-mono text-sm font-semibold text-slate-700">{complaint.id}</p>
      </div>

      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        {isParentWorkspace && (
          <Link
            to="/parent"
            className="rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-emerald-700"
          >
            내 민원 확인
          </Link>
        )}
        <button
          type="button"
          onClick={onWriteAnother}
          className="rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-bold text-slate-600 transition hover:border-emerald-200 hover:text-emerald-700"
        >
          추가 민원 작성
        </button>
      </div>
    </section>
  );
}
