import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
export const linkClass = "text-sky-700 underline decoration-sky-600/40 underline-offset-2 transition-colors duration-150 ease-out hover:decoration-sky-600 dark:text-sky-400 dark:decoration-sky-400/40 dark:hover:decoration-sky-400";
