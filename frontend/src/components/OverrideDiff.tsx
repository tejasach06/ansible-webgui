import type { OverrideValue } from "../lib/types";
import { formatValue } from "./KeyValueTable";

const labels: Record<string, string> = {
  credential_ids: "Credentials",
  diff: "Diff",
  extra_vars: "Extra vars",
  inventory_id: "Inventory",
  limit: "Limit",
  mode: "Mode",
  skip_tags: "Skip tags",
  tags: "Tags",
  verbosity: "Verbosity",
};

export function OverrideDiff({ overrides }: { overrides?: Record<string, OverrideValue> | null }) {
  const rows = Object.entries(overrides ?? {});
  if (!rows.length) return <p className="text-sm text-zinc-500 dark:text-zinc-400">No template overrides requested.</p>;

  return (
    <div className="overflow-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full border-collapse text-data">
        <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Field</th>
            <th className="px-3 py-2 text-left font-medium">Template</th>
            <th className="px-3 py-2 text-left font-medium">Requested</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {rows.map(([field, value]) => (
            <tr key={field} className="align-top">
              <td className="px-3 py-2 font-medium">{labels[field] ?? field}</td>
              <td className="px-3 py-2"><pre className="whitespace-pre-wrap font-mono">{formatValue(value.template)}</pre></td>
              <td className="px-3 py-2"><pre className="whitespace-pre-wrap font-mono">{formatValue(value.request)}</pre></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

