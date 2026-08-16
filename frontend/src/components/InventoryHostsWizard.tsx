import { useEffect, useMemo, useState } from "react";
import type { InventoryFormat } from "../lib/types";
import { Select, TextArea, TextInput } from "./Field";

export function parseHosts(value: string) {
  const seen = new Set<string>();
  return value.split(/[\s,]+/).map(h => h.trim()).filter(Boolean).filter(h => seen.has(h) ? false : (seen.add(h), true));
}

export function buildInventory(opts: { format: InventoryFormat; group: string; hosts: string[]; user?: string }): string {
  const group = opts.group.trim();
  const hosts = opts.hosts.map(h => h.trim()).filter(Boolean);
  const user = opts.user?.trim();
  if (opts.format === "ini") return `[${group}]\n${hosts.join("\n")}\n${user ? `\n[${group}:vars]\nansible_user=${user}\n` : ""}`;
  return `---\n${group}:\n  hosts:\n${hosts.map(h => `    ${h}:`).join("\n")}\n${user ? `  vars:\n    ansible_user: ${user}\n` : ""}`;
}

export function InventoryHostsWizard({ format, onChange }: { format: InventoryFormat; onChange: (content: string, valid: boolean) => void }) {
  const [group, setGroup] = useState("all");
  const [hostsText, setHostsText] = useState("");
  const [user, setUser] = useState("");
  const hosts = useMemo(() => parseHosts(hostsText), [hostsText]);
  const preview = buildInventory({ format, group, hosts, user });
  const valid = Boolean(group.trim() && hosts.length);
  useEffect(() => onChange(preview, valid), [preview, valid, onChange]);
  return <div className="grid gap-3"><TextInput id="inventory-group" label="Group name" value={group} onChange={e => setGroup(e.target.value)} /><TextArea id="inventory-hosts" label="Hosts" placeholder="web1.example.com, web2.example.com" value={hostsText} onChange={e => setHostsText(e.target.value)} /><TextInput id="inventory-user" label="SSH user (optional)" value={user} onChange={e => setUser(e.target.value)} /><Select id="inventory-host-format" label="Preview format" value={format} disabled><option value="yaml">yaml</option><option value="ini">ini</option></Select><pre className="overflow-auto rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-900">{preview}</pre></div>;
}
