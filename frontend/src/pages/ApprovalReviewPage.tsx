import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { FileCode } from "lucide-react";
import { useJob, useJobAction } from "../api/jobs";
import { Button } from "../components/Button";
import { ErrorBanner } from "../components/ErrorBanner";
import { TextArea } from "../components/Field";
import { JobSourceDialog } from "../components/JobSourceDialog";
import { KeyValueTable } from "../components/KeyValueTable";
import { OverrideDiff } from "../components/OverrideDiff";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { PanelSkeleton } from "../components/Skeleton";
import { StatusPill } from "../components/StatusPill";
import { ModeBadge } from "../components/ModeBadge";
import { useToast } from "../components/Toast";
import { useAuth } from "../lib/auth";
import { linkClass } from "../lib/cn";
import { runSummary } from "../lib/runSummary";
import { formatTimestamp } from "../lib/time";

export function ApprovalReviewPage() {
  const id = Number(useParams().jobId);
  const navigate = useNavigate();
  const { user, canAny } = useAuth();
  const { toast } = useToast();
  const job = useJob(id);
  const approve = useJobAction(id, "approve");
  const reject = useJobAction(id, "reject");
  const [note, setNote] = useState("");
  const [sourceOpen, setSourceOpen] = useState(false);
  const [sourceTab, setSourceTab] = useState<"playbook" | "inventory">("playbook");
  const openSource = (t: "playbook" | "inventory") => { setSourceTab(t); setSourceOpen(true); };

  const data = job.data;
  const ctx = data?.context;
  const snap = (data?.params_snapshot ?? {}) as Record<string, unknown>;
  const selfApproval = user?.id === data?.requested_by;

  const becomeParts: string[] = [];
  if (snap.become !== undefined && snap.become !== null) becomeParts.push(`become: ${snap.become}`);
  if (snap.become_user) becomeParts.push(`user: ${snap.become_user}`);
  if (snap.become_method) becomeParts.push(`method: ${snap.become_method}`);
  const becomeDisplay = becomeParts.length ? becomeParts.join(" · ") : "-";

  const limitValue = snap.limit !== undefined && snap.limit !== null && snap.limit !== "" ? String(snap.limit) : null;

  return (
    <section className="grid gap-6">
      <PageHeader
        title={`Approve job ${id}`}
        subtitle="Everything below is frozen at request time."
        status={data && <StatusPill status={data.status} />}
      />
      {job.isLoading && <PanelSkeleton />}
      {job.error && <ErrorBanner error={job.error} />}
      {(approve.error || reject.error) && <ErrorBanner error={approve.error || reject.error} />}
      {data && (
        <>
          <p className="max-w-[75ch] text-base leading-relaxed text-zinc-800 dark:text-zinc-200">{runSummary(data)}</p>
          <Section
            title="What will run"
            divider={false}
            actions={
              <Button variant="secondary" size="sm" icon={<FileCode size={16} strokeWidth={1.5} />} onClick={() => openSource("playbook")}>
                View playbook &amp; inventory
              </Button>
            }
          >
            <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-zinc-200 md:grid-cols-2 dark:bg-zinc-800">
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Project</dt>
                <dd className="mt-0.5 font-medium">{ctx?.project_name ?? "-"}</dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Playbook</dt>
                <dd className="mt-0.5">
                  <div className="font-medium">{ctx?.playbook_name ?? "-"}</div>
                  {ctx?.playbook_rel_path && (
                    <button type="button" className={`text-xs ${linkClass}`} onClick={() => openSource("playbook")}>
                      {ctx.playbook_rel_path}
                    </button>
                  )}
                </dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Inventory</dt>
                <dd className="mt-0.5">
                  <div className="font-medium">{ctx?.inventory_name ?? "-"}</div>
                  {ctx?.inventory_rel_path && (
                    <button type="button" className={`text-xs ${linkClass}`} onClick={() => openSource("inventory")}>
                      {ctx.inventory_rel_path}
                    </button>
                  )}
                </dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Template</dt>
                <dd className="mt-0.5 font-medium">{ctx?.template_name ?? "-"}</dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Mode</dt>
                <dd className="mt-0.5"><ModeBadge mode={data?.mode} /></dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Requested by</dt>
                <dd className="mt-0.5">{ctx?.requested_by_username ?? (data?.requested_by ? `#${data.requested_by}` : "-")}</dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Requested at</dt>
                <dd className="mt-0.5" title={data?.created_at ?? undefined}>{formatTimestamp(data?.created_at)}</dd>
              </div>
            </dl>
          </Section>

          <Section title="Execution parameters">
            <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-zinc-200 md:grid-cols-2 dark:bg-zinc-800">
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Limit</dt>
                <dd className="mt-0.5 font-mono">
                  {limitValue ? limitValue : <span className="text-amber-700 dark:text-amber-400">all hosts</span>}
                </dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Tags</dt>
                <dd className="mt-0.5 font-mono">{snap.tags ? String(snap.tags) : "-"}</dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Skip tags</dt>
                <dd className="mt-0.5 font-mono">{snap.skip_tags ? String(snap.skip_tags) : "-"}</dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Verbosity</dt>
                <dd className="mt-0.5 font-mono">{snap.verbosity !== undefined && snap.verbosity !== null ? `v${snap.verbosity}` : "-"}</dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Forks</dt>
                <dd className="mt-0.5 font-mono">{snap.forks !== undefined && snap.forks !== null ? String(snap.forks) : "-"}</dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Become</dt>
                <dd className="mt-0.5 font-mono">{becomeDisplay}</dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">Diff</dt>
                <dd className="mt-0.5 font-mono">{snap.diff !== undefined && snap.diff !== null ? String(snap.diff) : "-"}</dd>
              </div>
            </dl>
          </Section>

          <Section title="Extra vars">
            <KeyValueTable data={snap.extra_vars as Record<string, unknown> | null | undefined} empty="No extra vars." />
          </Section>

          <Section title="Credentials">
            {ctx?.credentials && ctx.credentials.length > 0 ? (
              <div className="grid gap-2">
                {ctx.credentials.map((cred) => (
                  <div key={cred.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
                    <span className="font-medium">{cred.name}</span>
                    <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">{cred.kind}</span>
                    <span className="text-xs text-fg-muted">{cred.username ?? "-"}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-fg-muted">No credentials selected.</p>
            )}
          </Section>

          <Section title="Pinned revisions">
            <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-zinc-200 md:grid-cols-2 dark:bg-zinc-800">
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">git_sha</dt>
                <dd className="mt-0.5 font-mono text-xs">{snap.git_sha ? String(snap.git_sha) : "-"}</dd>
              </div>
              <div className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
                <dt className="text-xs text-zinc-500 dark:text-zinc-400">inventory_commit_sha</dt>
                <dd className="mt-0.5 font-mono text-xs">{snap.inventory_commit_sha ? String(snap.inventory_commit_sha) : "-"}</dd>
              </div>
            </dl>
          </Section>

          <Section title="Template overrides">
            <OverrideDiff overrides={data.overrides} />
          </Section>

          {data.mode !== "check" && (
            <div role="note" className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200">
              Approving starts a live run against{" "}
              {limitValue ? <span className="font-mono">{limitValue}</span> : "every host in the inventory"}. Changes are not reversible from this app.
            </div>
          )}

          {data.status !== "pending_approval" ? (
            <Section title="Decision">
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
                This job is no longer awaiting approval. <Link className={linkClass} to={`/jobs/${id}`}>View job #{id}</Link>
              </div>
            </Section>
          ) : (
            <Section title="Decision">
              <div className="grid gap-3">
                <TextArea
                  id="approval-note"
                  label="Decision note (required)"
                  required
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="State the reason for approving or rejecting this run..."
                />
                {selfApproval && <p className="text-xs text-zinc-500 dark:text-zinc-400">You cannot approve your own request.</p>}
                <div className="flex gap-2">
                  <Button
                    disabled={!canAny("job.approve") || selfApproval || !note.trim()}
                    loading={approve.isPending}
                    onClick={() =>
                      approve.mutate(
                        { approval_note: note.trim() },
                        {
                          onSuccess: () => {
                            toast(`Approved job #${id}`);
                            navigate("/approvals");
                          },
                        }
                      )
                    }
                  >
                    Approve
                  </Button>
                  <Button
                    variant="danger"
                    disabled={!canAny("job.approve") || !note.trim()}
                    loading={reject.isPending}
                    onClick={() =>
                      reject.mutate(
                        { reason: note.trim() },
                        {
                          onSuccess: () => {
                            toast(`Rejected job #${id}`);
                            navigate("/approvals");
                          },
                        }
                      )
                    }
                  >
                    Reject
                  </Button>
                </div>
              </div>
            </Section>
          )}
          <JobSourceDialog jobId={id} open={sourceOpen} onClose={() => setSourceOpen(false)} initialTab={sourceTab} />
        </>
      )}
    </section>
  );
}

export default ApprovalReviewPage;
