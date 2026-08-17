import { useState } from "react"; import { Navigate, useLocation, useNavigate } from "react-router-dom"; import { Terminal, GitFork, ShieldCheck, KeyRound } from "lucide-react"; import { useAuth } from "../lib/auth"; import { Button } from "../components/Button"; import { TextInput } from "../components/Field"; import { ErrorBanner } from "../components/ErrorBanner";
const INVARIANTS = [
  { Icon: GitFork, title: "Git-pinned execution", body: "Live runs execute an exported git archive of the recorded commit, never a mutable working tree." },
  { Icon: ShieldCheck, title: "Two-person approval", body: "A job cannot be approved by the user who requested it." },
  { Icon: KeyRound, title: "Encrypted credentials", body: "Secrets stay encrypted at rest and are decrypted only into a short-lived worker directory." }
];
function HeroPanel({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <aside className="border-t border-zinc-800 bg-zinc-950 px-6 py-10 text-zinc-100 md:hidden" style={{ backgroundImage: "radial-gradient(80% 60% at 15% 0%, rgb(2 132 199 / 0.18), transparent 60%)" }}>
        <h2 className="text-xl font-semibold leading-tight tracking-tight text-zinc-100">Every run is pinned, reviewed, and logged.</h2>
        <div className="mt-6 divide-y divide-zinc-800">
          {INVARIANTS.map(({ Icon, title, body }) => (
            <div key={title} className="flex items-start gap-3 py-4 first:pt-0 last:pb-0">
              <Icon className="mt-0.5 h-5 w-5 shrink-0 text-sky-400" strokeWidth={1.5} aria-hidden="true" />
              <div>
                <h3 className="text-sm font-medium text-zinc-100">{title}</h3>
                <p className="mt-1 text-xs text-zinc-400">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </aside>
    );
  }
  return (
    <aside className="relative hidden overflow-hidden bg-zinc-950 px-12 py-16 text-zinc-100 md:flex md:flex-col md:justify-center" style={{ backgroundImage: "radial-gradient(80% 60% at 15% 0%, rgb(2 132 199 / 0.18), transparent 60%)" }}>
      <div className="max-w-md">
        <h2 className="max-w-[22ch] text-3xl font-semibold leading-tight tracking-tight text-zinc-100 md:text-4xl">Every run is pinned, reviewed, and logged.</h2>
        <div className="mt-8 divide-y divide-zinc-800">
          {INVARIANTS.map(({ Icon, title, body }) => (
            <div key={title} className="flex items-start gap-3 py-4 first:pt-0 last:pb-0">
              <Icon className="mt-1 h-5 w-5 shrink-0 text-sky-400" strokeWidth={1.5} aria-hidden="true" />
              <div>
                <h3 className="text-sm font-medium text-zinc-100">{title}</h3>
                <p className="mt-1 text-xs text-zinc-400">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
export function LoginPage(){const {user,login}=useAuth(); const nav=useNavigate(); const loc=useLocation(); const [username,setUsername]=useState(""); const [password,setPassword]=useState(""); const [loading,setLoading]=useState(false); const [error,setError]=useState<unknown>(); if(user)return <Navigate to="/" replace/>; return <main className="grid min-h-[100dvh] grid-cols-1 bg-white dark:bg-zinc-950 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]"><div className="flex items-center justify-center px-6 py-12 md:px-12"><form className="grid w-full max-w-sm gap-4" onSubmit={async e=>{e.preventDefault(); setLoading(true); setError(undefined); try{await login(username,password); nav(String((loc.state as {from?:{pathname:string}}|undefined)?.from?.pathname??"/"),{replace:true});}catch(err){setError(err)}finally{setLoading(false)}}}><div className="flex items-center gap-2"><Terminal className="h-5 w-5 text-sky-600 dark:text-sky-400" strokeWidth={1.5}/><span className="text-sm font-medium">Ansible WebGUI</span></div><div><h1 className="text-2xl font-semibold tracking-tight">Sign in</h1><p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Authenticate to request, approve, and watch playbook runs.</p></div><TextInput id="username" label="Username" value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username" autoFocus required/><TextInput id="password" label="Password" type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" required/>{error ? <ErrorBanner error={error}/> : null}<Button loading={loading} className="w-full">Sign in</Button></form></div><HeroPanel compact/><HeroPanel/></main>}
export default LoginPage;
