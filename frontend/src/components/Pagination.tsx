import { Button } from "./Button";

export function Pagination({ offset, limit, total, onChange }: { offset: number; limit: number; total: number; onChange: (next: number) => void }) {
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, total);
  return <div className="flex items-center justify-between gap-3 text-sm text-zinc-600 dark:text-zinc-400">
    <span>{start} to {end} of {total}</span>
    <div className="flex gap-2">
      <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</Button>
      <Button variant="secondary" size="sm" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next</Button>
    </div>
  </div>;
}
