import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Activity, Bell, ClipboardCheck, FolderGit2, History, Home, Menu, PlayCircle, Users } from "lucide-react";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { Button } from "./Button";

const NAV = [
  { to: "/", label: "Dashboard", icon: Home, perm: "read" },
  { to: "/projects", label: "Projects", icon: FolderGit2, perm: "read" },
  { to: "/jobs", label: "Jobs", icon: PlayCircle, perm: "read" },
  { to: "/approvals", label: "Approvals", icon: ClipboardCheck, perm: "read" },
  { to: "/notifications", label: "Notifications", icon: Bell, perm: "read" },
  { to: "/users", label: "Users", icon: Users, perm: "user.manage" },
  { to: "/audit", label: "Audit", icon: History, perm: "user.manage" },
];

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  return <nav className="grid gap-1">{NAV.filter((n) => can(n.perm)).map((n) => { const Icon = n.icon; return <NavLink key={n.to} to={n.to} end={n.to === "/"} onClick={onNavigate} className={({ isActive }) => `relative flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors duration-150 ease-out ${isActive ? "bg-zinc-100 dark:bg-zinc-800 before:absolute before:left-0 before:h-5 before:w-1 before:rounded-full before:bg-zinc-900 dark:before:bg-zinc-50" : "hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}><Icon size={16} strokeWidth={1.5} />{n.label}</NavLink>; })}</nav>;
}

export function AppShell({ children }: { children?: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const [mobile, setMobile] = useState(false);
  const themeSelect = <select aria-label="Theme" value={theme} onChange={(e) => setTheme(e.target.value as never)} className="rounded-lg border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select>;
  return <div className="grid min-h-[100dvh] grid-cols-1 bg-white dark:bg-zinc-950 md:grid-cols-[240px_1fr]"><a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:p-2 focus:text-sm dark:focus:bg-zinc-900">Skip to content</a><aside className="hidden border-r border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900 md:block"><div className="mb-4 flex items-center gap-2 px-2 text-xl font-semibold"><Activity size={18} strokeWidth={1.5} />Ansible WebGUI</div><NavList /></aside><div className="min-w-0"><div className="border-b border-zinc-200 p-3 dark:border-zinc-800 md:hidden"><div className="flex items-center justify-between gap-2"><div className="flex items-center gap-2 font-semibold"><Activity size={18} />Ansible WebGUI</div><Button aria-expanded={mobile} aria-controls="mobile-nav" variant="secondary" size="sm" icon={<Menu size={16} />} onClick={() => setMobile(!mobile)}>Menu</Button>{themeSelect}<Button variant="secondary" size="sm" onClick={logout}>Logout</Button></div>{mobile && <div id="mobile-nav" className="mt-3"><NavList onNavigate={() => setMobile(false)} /></div>}</div><header className="hidden items-center justify-between border-b border-zinc-200 px-6 py-3 text-sm dark:border-zinc-800 md:flex"><span>Signed in as <strong>{user?.username}</strong></span><div className="flex items-center gap-2">{themeSelect}<Button variant="secondary" size="sm" onClick={logout}>Logout</Button></div></header><main id="main" className="min-w-0 overflow-x-auto px-4 py-6 md:px-6">{children ?? <Outlet />}</main></div></div>;
}
