import type { KeyboardEvent } from "react";

export function Tabs<T extends string>({ tabs, value, onChange, labels, idPrefix = "tabs" }: { tabs: readonly T[]; value: T; onChange: (next: T) => void; labels: Record<T, string>; idPrefix?: string }) {
  const handleKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    const currentIndex = tabs.indexOf(value);
    if (currentIndex === -1) return;
    let nextIndex = currentIndex;
    if (e.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    else if (e.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") nextIndex = 0;
    else if (e.key === "End") nextIndex = tabs.length - 1;
    else return;
    e.preventDefault();
    const nextTab = tabs[nextIndex];
    onChange(nextTab);
    const btn = document.getElementById(`${idPrefix}-tab-${nextTab}`);
    btn?.focus();
  };

  return (
    <div className="border-b border-zinc-200 dark:border-zinc-800">
      <nav role="tablist" onKeyDown={handleKeyDown} className="-mb-px flex gap-4 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t}
            id={`${idPrefix}-tab-${t}`}
            role="tab"
            aria-selected={value === t}
            aria-controls={`${idPrefix}-panel-${t}`}
            tabIndex={value === t ? 0 : -1}
            onClick={() => onChange(t)}
            className={`whitespace-nowrap border-b-2 py-2 text-sm font-medium transition-colors duration-150 ease-out ${value === t ? "border-sky-600 text-zinc-900 dark:border-sky-400 dark:text-zinc-50" : "border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"}`}
          >
            {labels[t]}
          </button>
        ))}
      </nav>
    </div>
  );
}
