import { useEffect, useId, useRef, type ReactNode, type RefObject, type SyntheticEvent } from "react";
import { X } from "lucide-react";
import { Button } from "./Button";

export function Drawer({ open, onClose, onCancel, title, children, footer, initialFocusRef }: { open: boolean; onClose: () => void; onCancel?: (e: SyntheticEvent<HTMLDialogElement>) => void; title: string; children: ReactNode; footer?: ReactNode; initialFocusRef?: RefObject<HTMLElement> }) {
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
  return <dialog ref={ref} aria-labelledby={titleId} onClose={onClose} onCancel={onCancel} onClick={(e) => { if (e.target === ref.current) onClose(); }} className="ml-auto open:flex h-full w-[min(480px,100vw)] max-w-full flex-col translate-x-0 rounded-lg border-l border-zinc-200 bg-white p-0 shadow-overlay transition-transform duration-200 ease-out dark:border-zinc-800 dark:bg-zinc-900">
    <div className="flex shrink-0 items-center justify-between border-b border-zinc-200 bg-inherit px-4 py-3 dark:border-zinc-800"><h2 id={titleId} className="text-base font-semibold">{title}</h2><Button aria-label="Close" variant="ghost" size="sm" onClick={onClose} icon={<X size={16} strokeWidth={1.5} />} /></div>
    <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>{footer && <div className="shrink-0 border-t border-zinc-200 bg-inherit p-4 dark:border-zinc-800">{footer}</div>}
  </dialog>;
}
