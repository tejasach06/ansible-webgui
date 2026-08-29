import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { FileCode } from "lucide-react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { useJob, useJobAction, useJobReport, useRelaunchJob } from "../api/jobs";
import { useAuth } from "../lib/auth";
import { TERMINAL_JOB_STATUSES } from "../lib/types";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { Tabs } from "../components/Tabs";
import { StatusPill } from "../components/StatusPill";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Dialog } from "../components/Dialog";
import { JobSourceDialog } from "../components/JobSourceDialog";
import { TextInput } from "../components/Field";
import { TaskTree } from "../components/TaskTree";
import { HostMatrix } from "../components/HostMatrix";
import { ErrorBanner } from "../components/ErrorBanner";
import { linkClass } from "../lib/cn";
import { KeyValueTable } from "../components/KeyValueTable";
import { runSummary } from "../lib/runSummary";
import { formatTimestamp } from "../lib/time";

function JobLogTerminal({ jobId, status, rc, jumpCounter }: { jobId: number; status?: string; rc?: number | null; jumpCounter?: number | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const term = useRef<Terminal>();
  const last = useRef(0);
  const buffer = useRef<string[]>([]);
  const counters = useRef<number[]>([]);
  const truncated = useRef(false);
  const [down, setDown] = useState(false);
  const [query, setQuery] = useState("");
  const matches = counters.current.map((counter, index) => ({ counter, index, text: buffer.current[index] ?? "" })).filter((row) => query && row.text.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    if (!ref.current) return;
    const terminal = new Terminal({ convertEol: true, scrollback: 20000, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace', fontSize: 13, theme: { background: "#09090b", foreground: "#f4f4f5" } });
    const fit = new FitAddon();
    terminal.loadAddon(fit);
    terminal.open(ref.current);
    fit.fit();
    term.current = terminal;
    const source = new EventSource(`/api/jobs/${jobId}/events/stream?after_counter=0`);
    source.onmessage = (event) => {
      try {
        const evt = JSON.parse(event.data);
        if (evt.counter <= last.current) return;
        last.current = evt.counter;
        const text = evt.stdout ?? "";
        if (text) {
          buffer.current.push(text);
          counters.current.push(evt.counter);
          terminal.write(text);
          if (buffer.current.length > 5000) {
            buffer.current.shift();
            counters.current.shift();
            truncated.current = true;
          }
        }
      } catch { /* ignore malformed SSE frames */ }
    };
    const resize = () => fit.fit();
    window.addEventListener("resize", resize);
    return () => { source.close(); terminal.dispose(); window.removeEventListener("resize", resize); };
  }, [jobId]);

  useEffect(() => {
    if (jumpCounter && counters.current.length) {
      const index = counters.current.findIndex((counter) => counter >= jumpCounter);
      if (index >= 0) term.current?.scrollToLine(Math.max(0, index - 4));
    }
  }, [jumpCounter]);

  useEffect(() => {
    setDown(!TERMINAL_JOB_STATUSES.includes(status as never));
  }, [status]);

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="text-sm text-zinc-500 dark:text-zinc-400">{down ? `Stream closed${rc != null ? ` · rc ${rc}` : ""}` : "Streaming live output"}</div>
        <TextInput id="log-search" label="Search output" value={query} onChange={(event) => setQuery(event.target.value)} />
      </div>
      {query && <div className="text-xs text-zinc-500 dark:text-zinc-400">{matches.length} matches {matches.slice(0, 5).map((match) => <button key={match.counter} className={`ml-2 ${linkClass}`} onClick={() => term.current?.scrollToLine(Math.max(0, match.index - 4))}>#{match.counter}</button>)}</div>}
      {truncated.current && <div className="text-xs text-amber-600 dark:text-amber-400">Search buffer keeps the latest 5000 output lines.</div>}
      <div ref={ref} className="h-[620px] overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950 p-2" />
    </div>
  );
}

export function JobDetailPage() {
  const id = Number(useParams().jobId);
  const navigate = useNavigate();
  const { user, canAny } = useAuth();
  const job = useJob(id);
  const report = useJobReport(id);
  const approve = useJobAction(id, "approve");
  const reject = useJobAction(id, "reject");
  const cancel = useJobAction(id, "cancel");
  const relaunch = useRelaunchJob(id);
  const [approval, setApproval] = useState(false);
  const [note, setNote] = useState("");
  const [confirm, setConfirm] = useState<"reject" | "cancel" | "relaunch" | "failed" | null>(null);
  const [tab, setTab] = useState<"output" | "report" | "params">("output");
  const [jump, setJump] = useState<number | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [sourceTab, setSourceTab] = useState<"playbook" | "inventory">("playbook");
  const openSource = (t: "playbook" | "inventory") => { setSourceTab(t); setSourceOpen(true); };
  const data = job.data;
  const snapshot = data?.params_snapshot ?? {};
  const failedHosts = report.data?.hosts.filter((host) => ["failed", "unreachable"].includes(host.status)).map((host) => host.host) ?? [];
  const firstFailure = report.data?.hosts.find((host) => host.first_failure_counter)?.first_failure_counter;
  const rows = [
    ["Mode", data?.mode],
    ["Status", data?.status],
    ["Requested by", data?.requested_by],
    ["Approved by", data?.approved_by ?? "-"],
    ["Created", formatTimestamp(data?.created_at)],
    ["Started", formatTimestamp(data?.started_at)],
    ["Finished", formatTimestamp(data?.finished_at)],
    ["rc", data?.rc ?? "-"],
    ["git_sha", String(snapshot.git_sha ?? "-")],
    ["Relaunch of", data?.relaunch_of_id ? `#${data.relaunch_of_id}` : "-"],
  ];

  const jumpToOutput = (counter: number) => { setTab("output"); setJump(counter); };

  return (
    <section className="grid gap-4">
      <PageHeader
        title={`Job ${id}`}
        subtitle="Streamed output, host report, and the frozen launch parameters."
        status={data && <StatusPill status={data.status} />}
        actions={
          <Button variant="secondary" size="sm" icon={<FileCode size={16} strokeWidth={1.5} />} onClick={() => openSource("playbook")}>
            View playbook &amp; inventory
          </Button>
        }
      />
      {data && <p className="max-w-[75ch] text-base leading-relaxed text-zinc-800 dark:text-zinc-200">{runSummary(data)}</p>}
      {job.error && <ErrorBanner error={job.error} />}
      {report.error && <ErrorBanner error={report.error} />}
      <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-zinc-200 md:grid-cols-2 dark:bg-zinc-800">{rows.map(([key, value]) => <div key={key} className="bg-white px-3 py-2 text-sm dark:bg-zinc-950"><dt className="text-xs text-zinc-500 dark:text-zinc-400">{key}</dt><dd className="mt-0.5 font-mono">{String(value)}</dd></div>)}</dl>
      <div className="flex flex-wrap gap-2">
        {data?.status === "pending_approval" && canAny("job.approve") && <><Button disabled={data.requested_by === user?.id} title={data.requested_by === user?.id ? "You cannot approve a job you requested." : undefined} onClick={() => setApproval(true)}>Approve run</Button><Button variant="danger" onClick={() => setConfirm("reject")}>Reject</Button></>}
        {data && ["queued", "running"].includes(data.status) && canAny("job.cancel") && <Button variant="danger" onClick={() => setConfirm("cancel")}>Cancel</Button>}
        {data && TERMINAL_JOB_STATUSES.includes(data.status) && canAny("job.request") && <><Button variant="secondary" title={`Original sha ${String(snapshot.git_sha ?? "").slice(0, 8)}`} onClick={() => setConfirm("relaunch")}>Relaunch</Button><Button variant="secondary" disabled={!failedHosts.length} title={failedHosts.length ? `Limit ${failedHosts.join(",")}; sha ${String(snapshot.git_sha ?? "").slice(0, 8)}` : "No failed hosts"} onClick={() => setConfirm("failed")}>Relaunch failed hosts</Button></>}
      </div>
      <Tabs tabs={["output", "report", "params"] as const} value={tab} onChange={setTab} labels={{ output: "Output", report: "Report", params: "Params" }} />
      {tab === "report" && firstFailure && <div className="flex flex-wrap gap-2"><Button size="sm" variant="secondary" onClick={() => jumpToOutput(firstFailure)}>Jump to first failure</Button></div>}
      {tab === "output" && <JobLogTerminal jobId={id} status={data?.status} rc={data?.rc} jumpCounter={jump} />}
      {tab === "report" && <div className="grid gap-4"><HostMatrix data={report.data} onJump={jumpToOutput} /><TaskTree data={report.data} onJump={jumpToOutput} /></div>}
      {tab === "params" && <KeyValueTable data={snapshot} empty="No launch parameters recorded." />}
      <Dialog open={approval} onClose={() => { setApproval(false); setNote(""); }} title="Approve run"><TextInput id="note" label="Approval note" value={note} onChange={(event) => setNote(event.target.value)} /><div className="mt-4 flex justify-end gap-2"><Button variant="secondary" onClick={() => setApproval(false)}>Cancel</Button><Button disabled={!note.trim()} loading={approve.isPending} onClick={() => approve.mutate({ approval_note: note.trim() }, { onSuccess: () => { setApproval(false); setNote(""); } })}>Approve</Button></div></Dialog>
      <ConfirmDialog open={!!confirm} title={confirm === "reject" ? "Reject job?" : confirm === "cancel" ? "Cancel job?" : confirm === "failed" ? "Relaunch failed hosts?" : "Relaunch job?"} name={confirm === "failed" ? `${failedHosts.join(",")} @ ${String(snapshot.git_sha ?? "").slice(0, 8)}` : `job ${id}`} onClose={() => setConfirm(null)} onConfirm={() => { if (confirm === "reject") reject.mutate(undefined, { onSuccess: () => setConfirm(null) }); if (confirm === "cancel") cancel.mutate(undefined, { onSuccess: () => setConfirm(null) }); if (confirm === "relaunch") relaunch.mutate({ hosts: "all" }, { onSuccess: (result) => navigate(`/jobs/${result.id}`) }); if (confirm === "failed") relaunch.mutate({ hosts: "failed" }, { onSuccess: (result) => navigate(`/jobs/${result.id}`) }); }} />
      {data && <JobSourceDialog jobId={id} open={sourceOpen} onClose={() => setSourceOpen(false)} initialTab={sourceTab} />}
    </section>
  );
}

export default JobDetailPage;
