import { useEffect, useState } from "react";
import Editor from "@monaco-editor/react";
import { useJobSource } from "../api/jobs";
import { Dialog } from "./Dialog";
import { ErrorBanner } from "./ErrorBanner";
import { PanelSkeleton } from "./Skeleton";
import { Tabs } from "./Tabs";
import { useTheme } from "../lib/theme";

const SOURCE_ERRORS: Record<string, string> = {
  revision_not_found:
    "The revision pinned for this run is no longer in the repository (history was rewritten or the repo was replaced). Reject this request and relaunch it so it pins a current revision.",
  file_not_found_at_revision:
    "This file does not exist at the revision pinned for this run. Reject this request and relaunch it from the current project content.",
  file_too_large:
    "File is larger than 512 KB, so it is not shown here. Open it in the project workspace instead.",
  repo_not_found:
    "The repository for this file is not available on this server. Check the content volume before approving.",
};

export function JobSourceDialog({ jobId, open, onClose, initialTab = "playbook" }: { jobId: number; open: boolean; onClose: () => void; initialTab?: "playbook" | "inventory" }) {
  const src = useJobSource(jobId, open);
  const { effectiveTheme } = useTheme();
  const [tab, setTab] = useState<"playbook" | "inventory">(initialTab);

  useEffect(() => {
    if (open) setTab(initialTab);
  }, [open, initialTab]);
  if (!open) return null;

  const file = tab === "playbook" ? src.data?.playbook : src.data?.inventory;
  const errorMsg = file?.error ? (SOURCE_ERRORS[file.error] ?? `This file could not be loaded (${file.error}).`) : null;

  return (
    <Dialog open={open} onClose={onClose} title={`Job #${jobId} source`} size="full">
      <div className="flex min-h-0 flex-1 flex-col gap-3">
        <Tabs
          tabs={["playbook", "inventory"] as const}
          value={tab}
          onChange={setTab}
          labels={{ playbook: "Playbook", inventory: "Inventory" }}
        />
        <div role="tabpanel" aria-label={tab === "playbook" ? "Playbook" : "Inventory"} className="flex min-h-0 flex-1 flex-col">
          {src.error && <ErrorBanner error={src.error} />}
          {src.isLoading && <PanelSkeleton />}
          {src.data && file === null && (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              {tab === "inventory"
                ? "This job runs without an inventory file; hosts come from the playbook and limit."
                : "No playbook is recorded for this job."}
            </p>
          )}
          {file && (
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 pb-2">
                <span className="font-mono text-sm">{file.rel_path}</span>
                <span className="font-mono text-xs text-zinc-500 dark:text-zinc-400">
                  {file.sha ? file.sha.slice(0, 10) : "revision unknown"}
                </span>
                <span className="text-xs text-zinc-500 dark:text-zinc-400">frozen at request time</span>
              </div>
              {errorMsg ? (
                <p className="text-sm text-amber-700 dark:text-amber-400">{errorMsg}</p>
              ) : (
                <>
                  {file.is_vault && (
                    <p className="pb-2 text-sm text-amber-700 dark:text-amber-400">
                      Vault-encrypted file. The ciphertext is shown; the plaintext is only decrypted by the runner.
                    </p>
                  )}
                  <div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
                    <Editor
                      height="100%"
                      language="yaml"
                      value={file.content ?? ""}
                      theme={effectiveTheme === "dark" ? "vs-dark" : "light"}
                      options={{
                        readOnly: true,
                        domReadOnly: true,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        wordWrap: "on",
                        renderLineHighlight: "none",
                        lineNumbersMinChars: 3,
                        fontSize: 13,
                      }}
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </Dialog>
  );
}
