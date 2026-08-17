import { useState } from "react";
import { Button } from "./Button";
import type { JobReport } from "../lib/types";

function duration(ms: number) {
  if (ms >= 60000) return `${(ms / 60000).toFixed(1)}m`;
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

export function TaskTree({ data, onJump }: { data?: JobReport; onJump: (counter: number) => void }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [slowestFirst, setSlowestFirst] = useState(false);
  if (!data?.plays.length) return <p className="text-sm text-zinc-500">No task events yet.</p>;

  return (
    <div className="grid gap-3">
      <div className="flex justify-end">
        <Button size="sm" variant="secondary" onClick={() => setSlowestFirst(!slowestFirst)}>
          {slowestFirst ? "Original order" : "Slowest first"}
        </Button>
      </div>
      {data.plays.map((play, index) => {
        const key = play.uuid ?? String(index);
        const shown = open[key] ?? true;
        const tasks = slowestFirst ? [...play.tasks].sort((a, b) => b.duration_ms - a.duration_ms) : play.tasks;
        return (
          <div key={key} className="rounded-lg border border-zinc-200 dark:border-zinc-800">
            <button className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left font-medium" onClick={() => setOpen({ ...open, [key]: !shown })}>
              <span>{shown ? "▾" : "▸"} {play.name ?? "Play"}</span>
              <span className="text-xs font-normal text-zinc-500">{duration(play.duration_ms)}</span>
            </button>
            {shown && (
              <div className="grid gap-2 p-3">
                {tasks.map((task) => (
                  <div key={task.uuid ?? task.name ?? task.action} className="grid gap-2 rounded border border-zinc-100 p-2 text-sm dark:border-zinc-800">
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <div className="font-medium">{task.name ?? "Task"}</div>
                        <div className="text-xs text-zinc-500">{task.action ?? "—"} · {duration(task.duration_ms)}</div>
                      </div>
                      {task.first_failure_counter && <Button size="sm" variant="secondary" onClick={() => onJump(task.first_failure_counter!)}>First failure</Button>}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(task.results).map(([status, count]) => (
                        <span key={status} className={count && ["failed", "unreachable"].includes(status) ? "rounded bg-red-100 px-2 py-1 text-xs text-red-800 dark:bg-red-950 dark:text-red-200" : "rounded bg-zinc-100 px-2 py-1 text-xs dark:bg-zinc-800"}>
                          {status}: {count}
                        </span>
                      ))}
                    </div>
                    {task.failed_hosts.length > 0 && <div className="text-xs text-red-700 dark:text-red-300">Failed hosts: {task.failed_hosts.join(", ")}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default TaskTree;
