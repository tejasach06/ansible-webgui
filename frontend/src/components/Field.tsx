import { forwardRef, type InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes, ReactNode } from "react";
import { cn } from "../lib/cn";
function wrap(id:string,label:string,error:ReactNode|undefined,children:ReactNode){return <label className="grid gap-1 text-sm" htmlFor={id}><span className="font-medium">{label}</span>{children}{error&&<span id={`${id}-error`} className="text-xs text-red-700 dark:text-red-300">{error}</span>}</label>}
const base="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100";
export const TextInput=forwardRef<HTMLInputElement,InputHTMLAttributes<HTMLInputElement>&{id:string;label:string;error?:ReactNode}>(({id,label,error,className,...p},ref)=>wrap(id,label,error,<input ref={ref} id={id} aria-invalid={!!error} aria-describedby={error?`${id}-error`:undefined} className={cn(base,className)} {...p}/>));
TextInput.displayName="TextInput";
export const NumberInput=forwardRef<HTMLInputElement,InputHTMLAttributes<HTMLInputElement>&{id:string;label:string;error?:ReactNode}>((p,ref)=><TextInput ref={ref} type="number" {...p}/>);
NumberInput.displayName="NumberInput";
export const TextArea=forwardRef<HTMLTextAreaElement,TextareaHTMLAttributes<HTMLTextAreaElement>&{id:string;label:string;error?:ReactNode}>(({id,label,error,className,...p},ref)=>wrap(id,label,error,<textarea ref={ref} id={id} aria-invalid={!!error} aria-describedby={error?`${id}-error`:undefined} className={cn(base,"min-h-24 font-mono",className)} {...p}/>));
TextArea.displayName="TextArea";
export const Select=forwardRef<HTMLSelectElement,SelectHTMLAttributes<HTMLSelectElement>&{id:string;label:string;error?:ReactNode}>(({id,label,error,className,children,...p},ref)=>wrap(id,label,error,<select ref={ref} id={id} aria-invalid={!!error} aria-describedby={error?`${id}-error`:undefined} className={cn(base,className)} {...p}>{children}</select>));
Select.displayName="Select";
export function Checkbox({id,label,error,className,...p}:InputHTMLAttributes<HTMLInputElement>&{id:string;label:string;error?:ReactNode}){return <label className="flex items-center gap-2 text-sm" htmlFor={id}><input id={id} type="checkbox" aria-invalid={!!error} aria-describedby={error?`${id}-error`:undefined} className={cn("h-4 w-4 rounded border-zinc-300",className)} {...p}/><span>{label}</span>{error&&<span id={`${id}-error`} className="text-xs text-red-700">{error}</span>}</label>}
