import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import {
  becomeCoveredByMachine,
  credentialLabel,
  EMPTY_SLOTS,
  fromSlots,
  SLOT_LABEL,
  SLOT_ORDER,
  slotOptions,
  toSlots,
  type CredentialSlot,
  type SlotSelection,
} from "../lib/credentialSlots";
import type { Credential } from "../lib/types";
import { Select } from "./Field";

export function CredentialSlots({
  credentials,
  value,
  onChange,
  disabled = false,
  idPrefix,
  autoSelectMachine = false,
  emptyCta = false,
}: {
  credentials: Credential[] | undefined;
  value: number[];
  onChange: (ids: number[]) => void;
  disabled?: boolean;
  idPrefix: string;
  autoSelectMachine?: boolean;
  emptyCta?: boolean;
}) {
  const all = credentials ?? [];
  const sel = toSlots(all, value);
  const machine = all.find((c) => c.id === sel.machine);

  const lastCredsRef = useRef<Credential[] | undefined>(undefined);
  const didAutoSelectRef = useRef(false);

  useEffect(() => {
    if (credentials !== lastCredsRef.current) {
      lastCredsRef.current = credentials;
      didAutoSelectRef.current = false;
    }
    if (autoSelectMachine && !disabled && !didAutoSelectRef.current && sel.machine === null) {
      const machineOptions = slotOptions(all, "machine", undefined);
      if (machineOptions.length === 1) {
        didAutoSelectRef.current = true;
        onChange(fromSlots({ ...EMPTY_SLOTS, ...sel, machine: machineOptions[0].id }));
      }
    }
  }, [credentials, value, disabled, autoSelectMachine, onChange]);

  if (all.length === 0 && emptyCta) {
    return (
      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        No credentials in this project.{" "}
        <Link to="/credentials" className="underline">
          Add one
        </Link>
        .
      </p>
    );
  }

  const handleSlotChange = (slot: CredentialSlot, rawValue: string) => {
    const valueOrNull = rawValue ? Number(rawValue) : null;
    const next: SlotSelection = { ...sel, [slot]: valueOrNull };
    const nextMachine = all.find((c) => c.id === next.machine);

    if (becomeCoveredByMachine(nextMachine)) {
      next.become = null;
    }

    for (const s of ["vault", "become"] as const) {
      if (next[s] !== null) {
        const validIds = new Set(slotOptions(all, s, nextMachine).map((c) => c.id));
        if (!validIds.has(next[s]!)) {
          next[s] = null;
        }
      }
    }

    onChange(fromSlots(next));
  };

  return (
    <div className="grid gap-3">
      {SLOT_ORDER.map((slot) => {
        if (slot === "become" && becomeCoveredByMachine(machine)) {
          return (
            <p key={slot} className="text-xs text-zinc-500 dark:text-zinc-400">
              Sudo uses the SSH password from {machine?.name}.
            </p>
          );
        }

        const options = slotOptions(all, slot, machine);
        const currentVal = sel[slot] !== null ? String(sel[slot]) : "";

        return (
          <Select
            key={slot}
            id={`${idPrefix}-${slot}`}
            label={SLOT_LABEL[slot]}
            value={currentVal}
            disabled={disabled}
            onChange={(e) => handleSlotChange(slot, e.target.value)}
          >
            <option value="">None</option>
            {options.map((c) => (
              <option key={c.id} value={c.id}>
                {credentialLabel(c)}
              </option>
            ))}
          </Select>
        );
      })}
    </div>
  );
}
