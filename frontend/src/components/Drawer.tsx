import { useEffect, useId, useRef, type ReactNode, type RefObject } from "react";
import { X } from "lucide-react";
import { Button } from "./Button";

export function Drawer({ open, onClose, title, children, footer, initialFocusRef }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; initialFocusRef?: RefObject<HTMLElement> }) {
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
  return <dialog ref={ref} aria-labelledby={titleId} onClose={onClose} className="ml-auto h-full w-[480px] max-w-full translate-x-0 rounded-lg border-l border-zinc-200 bg-white p-0 shadow-overlay transition-transform duration-200 ease-out dark:border-zinc-800 dark:bg-zinc-900">
    <div className="sticky top-0 flex items-center justify-between border-b border-zinc-200 bg-inherit px-4 py-3 dark:border-zinc-800"><h2 id={titleId} className="text-base font-semibold">{title}</h2><Button aria-label="Close" variant="ghost" size="sm" onClick={onClose} icon={<X size={16} strokeWidth={1.5} />} /></div>
    <div className="p-4">{children}</div>{footer && <div className="sticky bottom-0 border-t border-zinc-200 bg-inherit p-4 dark:border-zinc-800">{footer}</div>}
  </dialog>;
}
