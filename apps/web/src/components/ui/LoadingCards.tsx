export function LoadingCards({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3" aria-label="민원 목록을 불러오는 중" aria-busy="true">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="animate-pulse rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex gap-2">
            <div className="h-6 w-14 rounded-full bg-slate-100" />
            <div className="h-6 w-20 rounded-full bg-slate-100" />
          </div>
          <div className="mt-4 h-5 w-2/5 rounded bg-slate-100" />
          <div className="mt-3 h-4 w-full rounded bg-slate-100" />
          <div className="mt-2 h-4 w-3/4 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}
