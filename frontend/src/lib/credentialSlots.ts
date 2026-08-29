import type { Credential, CredentialKind } from "./types";

export type CredentialSlot = "machine" | "vault" | "become";

export const SLOT_ORDER: CredentialSlot[] = ["machine", "vault", "become"];

export const SLOT_LABEL: Record<CredentialSlot, string> = {
  machine: "Machine credential (SSH)",
  vault: "Vault password",
  become: "Become (sudo) password",
};

export const KIND_LABEL: Record<CredentialKind, string> = {
  ssh_key: "SSH key",
  ssh_password: "SSH password",
  vault_password: "Vault password",
  become_password: "Become (sudo) password",
};

const KIND_SLOT: Record<CredentialKind, CredentialSlot> = {
  ssh_key: "machine",
  ssh_password: "machine",
  vault_password: "vault",
  become_password: "become",
};

export type SlotSelection = Record<CredentialSlot, number | null>;

export const EMPTY_SLOTS: SlotSelection = { machine: null, vault: null, become: null };

export function slotOf(kind: CredentialKind): CredentialSlot {
  return KIND_SLOT[kind];
}

/** Project flat wire list onto slots. First id matching slot wins; unknown ids dropped. */
export function toSlots(all: Credential[], ids: number[]): SlotSelection {
  const map = new Map(all.map((c) => [c.id, c]));
  const sel: SlotSelection = { machine: null, vault: null, become: null };
  for (const id of ids) {
    const cred = map.get(id);
    if (!cred) continue;
    const slot = slotOf(cred.kind);
    if (sel[slot] === null) {
      sel[slot] = id;
    }
  }
  return sel;
}

/** Flatten slots back to wire list in SLOT_ORDER, skipping nulls. */
export function fromSlots(sel: SlotSelection): number[] {
  const res: number[] = [];
  for (const slot of SLOT_ORDER) {
    const id = sel[slot];
    if (id !== null && id !== undefined) {
      res.push(id);
    }
  }
  return res;
}

/** Options offered for slot, filtering username conflicts with selected machine credential. */
export function slotOptions(
  all: Credential[],
  slot: CredentialSlot,
  machine: Credential | undefined,
): Credential[] {
  return all.filter((c) => {
    if (slotOf(c.kind) !== slot) return false;
    if (slot !== "machine" && machine?.username && c.username && c.username !== machine.username) {
      return false;
    }
    return true;
  });
}

/** True when machine credential already covers sudo (ssh_password with become_same_as_ssh). */
export function becomeCoveredByMachine(machine: Credential | undefined): boolean {
  return machine !== undefined && machine.kind === "ssh_password" && Boolean(machine.become_same_as_ssh);
}

/** Standard credential option label. */
export function credentialLabel(c: Credential): string {
  return `${c.name} — ${c.kind}${c.username ? ` (user: ${c.username})` : ""}`;
}
