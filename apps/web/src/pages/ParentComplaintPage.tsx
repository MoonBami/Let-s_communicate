import { useForm } from 'react-hook-form';
import { useMutation } from '@tanstack/react-query';
import { API, type CreateComplaintRequest, type Complaint } from '@sotong/shared';
import { api } from '@/lib/api';

// 학부모 민원 접수 화면 (F1 진입점). 제출하면 백엔드에서 분류·필터를 거침.
export function ParentComplaintPage() {
  const { register, handleSubmit, reset, formState } = useForm<CreateComplaintRequest>();

  const mutation = useMutation({
    mutationFn: async (payload: CreateComplaintRequest) => {
      const { data } = await api.post<Complaint>(API.complaints.create, payload);
      return data;
    },
    onSuccess: () => reset(),
  });

  return (
    <div className="mx-auto max-w-xl px-4 py-10">
      <h1 className="text-xl font-bold mb-1">민원 접수</h1>
      <p className="text-sm text-slate-500 mb-6">
        접수된 내용은 AI 분류·검토를 거쳐 담당 교사에게 전달됩니다.
      </p>

      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
        <input type="hidden" {...register('schoolId')} value="DEMO_SCHOOL_ID" />
        <label className="block space-y-1">
          <span className="text-sm text-slate-600">제목</span>
          <input
            {...register('title')}
            className="w-full rounded-md border px-3 py-2 text-sm"
            placeholder="예: 급식 알레르기 문의"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm text-slate-600">내용 *</span>
          <textarea
            {...register('body', { required: true, minLength: 5 })}
            rows={6}
            className="w-full rounded-md border px-3 py-2 text-sm"
            placeholder="민원 내용을 입력해 주세요."
          />
        </label>

        {mutation.isSuccess && (
          <p className="text-sm text-green-600">접수 완료. 검토 후 안내드리겠습니다.</p>
        )}
        {mutation.isError && (
          <p className="text-sm text-red-600">접수 실패 (백엔드 연동 후 동작)</p>
        )}

        <button
          type="submit"
          disabled={mutation.isPending || formState.isSubmitting}
          className="rounded-md bg-brand text-white px-4 py-2 text-sm font-medium hover:bg-brand-fg disabled:opacity-50"
        >
          {mutation.isPending ? '접수 중...' : '접수하기'}
        </button>
      </form>
    </div>
  );
}
