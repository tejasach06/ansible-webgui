import type { ReactNode } from "react";

export function PageHeader({ title, subtitle, status, actions }: { title: ReactNode; subtitle?: string; status?: ReactNode; actions?: ReactNode }) {
  return <div className="flex flex-wrap items-start justify-between gap-3">
    <div className="grid gap-1">
      <div className="flex flex-wrap items-center gap-2"><h1 className="text-2xl font-semibold tracking-tight">{title}</h1>{status}</div>
      {subtitle && <p className="max-w-[65ch] text-sm text-zinc-500 dark:text-zinc-400">{subtitle}</p>}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
  </div>;
}
