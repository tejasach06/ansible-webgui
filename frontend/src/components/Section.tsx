import type { ReactNode } from "react";

export function Section({ title, actions, divider = true, children }: { title: string; actions?: ReactNode; divider?: boolean; children: ReactNode }) {
  return <section className={divider ? "grid gap-3 border-t border-zinc-200 pt-5 dark:border-zinc-800" : "grid gap-3"}>
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold tracking-tight">{title}</h2>{actions}</div>
    {children}
  </section>;
}
