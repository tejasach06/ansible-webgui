import type { ReactNode } from "react"; import { useAuth } from "../lib/auth"; export function Can({perm,children}:{perm:string;children:ReactNode}){return useAuth().can(perm)?<>{children}</>:null}
