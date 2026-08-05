import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  API,
  ESCALATION_STATUS_LABEL,
  type Escalation,
  type UpdateEscalationRequest,
} from '@sotong/shared';
import { api } from '@/lib/api';

// F8 이관 관리 — 관리자·MDT 전용. 교사가 넘긴 민원을 접수/해결/반송한다.
export function EscalationsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['escalations'],
    queryFn: async () => {
      const { data } = await api.get<Escalation[]>(API.escalations.list);
      return data;
    },
  });

  const update = useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: UpdateEscalationRequest }) => {
      const { data } = await api.patch<Escalation>(API.escalations.update(id), payload);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['escalations'] }),
  });

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">이관 관리</h1>

      {isLoading && <p className="text-sm text-slate-500">불러오는 중...</p>}
      {isError && <p className="text-sm text-red-600">목록을 불러오지 못했습니다.</p>}

      <div className="space-y-2">
        {data?.map((e) => {
          const open = e.status === 'requested' || e.status === 'accepted';
          return (
            <article key={e.id} className="rounded-lg border bg-white p-4">
              <div className="flex items-center gap-2 mb-2 text-xs">
                <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                  {ESCALATION_STATUS_LABEL[e.status]}
                </span>
                <Link
                  to={`/complaints/${e.complaintId}`}
                  className="text-brand hover:underline"
                >
                  민원 보기
                </Link>
                <span className="text-slate-400 ml-auto">
                  {new Date(e.createdAt).toLocaleString('ko-KR')}
                </span>
              </div>

              <p className="text-sm">
                <span className="text-slate-500">사유: </span>
                {e.reason ?? '(없음)'}
              </p>
              {e.resolution && (
                <p className="text-sm mt-1">
                  <span className="text-slate-500">처리: </span>
                  {e.resolution}
                </p>
              )}

              {open && (
                <div className="flex gap-2 mt-3">
                  {e.status === 'requested' && (
                    <ActionButton
                      onClick={() => update.mutate({ id: e.id, payload: { status: 'accepted' } })}
                      disabled={update.isPending}
                    >
                      접수
                    </ActionButton>
                  )}
                  <ActionButton
                    onClick={() => update.mutate({ id: e.id, payload: { status: 'resolved' } })}
                    disabled={update.isPending}
                  >
                    해결 처리
                  </ActionButton>
                  <ActionButton
                    onClick={() => update.mutate({ id: e.id, payload: { status: 'rejected' } })}
                    disabled={update.isPending}
                  >
                    교사에게 반송
                  </ActionButton>
                </div>
              )}
            </article>
          );
        })}
        {data && data.length === 0 && (
          <p className="text-sm text-slate-500">이관된 민원이 없습니다.</p>
        )}
      </div>
    </div>
  );
}

function ActionButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
    >
      {children}
    </button>
  );
}
