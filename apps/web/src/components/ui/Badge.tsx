import type { ReactNode } from 'react';

export type BadgeTone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger';

const toneClasses: Record<BadgeTone, string> = {
  neutral: 'bg-slate-100 text-slate-600 ring-slate-200',
  brand: 'bg-blue-50 text-blue-700 ring-blue-100',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
  warning: 'bg-amber-50 text-amber-700 ring-amber-100',
  danger: 'bg-red-50 text-red-700 ring-red-100',
};

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: BadgeTone }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}
