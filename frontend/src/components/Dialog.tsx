import { useEffect, useId, useRef, type ReactNode, type RefObject, type SyntheticEvent } from "react";
import { X } from "lucide-react";
import { Button } from "./Button";

type DialogSize = "md" | "full";

type DialogProps = { open: boolean; onClose: () => void; title: string; children: ReactNode; initialFocusRef?: RefObject<HTMLElement>; size?: DialogSize; onCancel?: (e: SyntheticEvent<HTMLDialogElement>) => void };

export function Dialog({ open, onClose, title, children, initialFocusRef, size = "md", onCancel }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
      initialFocusRef?.current?.focus();
    }
    if (!open && d.open) d.close();
  }, [open, initialFocusRef]);
  return <dialog ref={ref} aria-labelledby={titleId} onClose={onClose} onCancel={onCancel} onClick={(e) => { if (e.target === ref.current) onClose(); }} className={size === "full" ? "open:flex h-[90vh] w-[90vw] max-w-none flex-col rounded-lg border border-zinc-200 bg-white p-0 shadow-overlay dark:border-zinc-800 dark:bg-zinc-900" : "open:flex max-h-[85dvh] w-[640px] max-w-[calc(100%-2rem)] flex-col rounded-lg border border-zinc-200 bg-white p-0 shadow-overlay dark:border-zinc-800 dark:bg-zinc-900"}>
    <div className="flex shrink-0 items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800"><h2 id={titleId} className="text-base font-semibold">{title}</h2><Button aria-label="Close" variant="ghost" size="sm" onClick={onClose} icon={<X size={16} strokeWidth={1.5} />} /></div>
    <div className={size === "full" ? "flex min-h-0 flex-1 flex-col overflow-y-auto p-4" : "min-h-0 flex-1 overflow-y-auto p-4"}>{children}</div>
  </dialog>;
}
