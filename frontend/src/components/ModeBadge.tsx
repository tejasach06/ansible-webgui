export function ModeBadge({ mode }: { mode?: string | null }) {
  if (!mode) return <span className="text-fg-muted">-</span>;
  const live = mode !== "check";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
        live
          ? "bg-red-100 text-red-900 dark:bg-red-500/15 dark:text-red-200"
          : "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
      }`}
    >
      {live ? "Live — changes hosts" : "Check — no changes"}
    </span>
  );
}
