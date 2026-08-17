export function Tabs<T extends string>({ tabs, value, onChange, labels }: { tabs: readonly T[]; value: T; onChange: (next: T) => void; labels: Record<T, string> }) {
  return <div className="border-b border-zinc-200 dark:border-zinc-800">
    <nav role="tablist" className="-mb-px flex gap-4 overflow-x-auto">
      {tabs.map((t) => <button key={t} role="tab" aria-selected={value === t} onClick={() => onChange(t)} className={`whitespace-nowrap border-b-2 py-2 text-sm font-medium transition-colors duration-150 ease-out ${value === t ? "border-sky-600 text-zinc-900 dark:border-sky-400 dark:text-zinc-50" : "border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"}`}>{labels[t]}</button>)}
    </nav>
  </div>;
}
