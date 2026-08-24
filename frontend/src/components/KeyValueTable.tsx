export function humanKey(key: string): string {
  const s = key.replace(/[_-]+/g, " ");
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}

function isScalar(val: unknown): boolean {
  return val === null || val === undefined || typeof val !== "object";
}

function format(value: unknown, depth = 0): string {
  const indent = "  ".repeat(depth);
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string" || typeof value === "number") return String(value);

  if (Array.isArray(value)) {
    if (value.length === 0) return "-";
    if (value.every(isScalar)) {
      return value.map((x) => (x === null || x === undefined || x === "" ? "-" : typeof x === "boolean" ? (x ? "Yes" : "No") : String(x))).join(", ");
    }
    return value.map((entry) => `${indent}${format(entry, depth + 1)}`).join("\n");
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return "-";
    return entries
      .map(([k, v]) => {
        if (v !== null && typeof v === "object" && !Array.isArray(v) && Object.keys(v).length > 0) {
          return `${indent}${humanKey(k)}:\n${format(v, depth + 1)}`;
        }
        return `${indent}${humanKey(k)}: ${format(v, depth + 1)}`;
      })
      .join("\n");
  }

  return String(value);
}

export function formatValue(value: unknown): string {
  return format(value, 0);
}

export function KeyValueTable({
  data,
  empty,
}: {
  data?: Record<string, unknown> | null;
  empty: string;
}) {
  const entries = Object.entries(data ?? {});
  if (!entries.length) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">{empty}</p>;
  }

  const sorted = [...entries].sort(([a], [b]) => a.localeCompare(b));

  return (
    <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg bg-zinc-200 md:grid-cols-2 dark:bg-zinc-800">
      {sorted.map(([key, value]) => (
        <div key={key} className="bg-white px-3 py-2 text-sm dark:bg-zinc-950">
          <dt className="text-xs text-zinc-500 dark:text-zinc-400">{humanKey(key)}</dt>
          <dd className="mt-0.5 whitespace-pre-wrap font-mono">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
