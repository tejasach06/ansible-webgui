import { KIND_LABEL } from "./credentialSlots";
import type { CredentialKind } from "./types";

function assertStrictEqual(actual: unknown, expected: unknown) {
  if (actual !== expected) {
    throw new Error(`Assertion failed:\nExpected: ${JSON.stringify(expected)}\nActual:   ${JSON.stringify(actual)}`);
  }
}

const kinds: CredentialKind[] = ["ssh_key", "ssh_password", "vault_password", "become_password"];

for (const k of kinds) {
  if (!KIND_LABEL[k]) {
    throw new Error(`Missing KIND_LABEL mapping for kind: ${k}`);
  }
}

assertStrictEqual(KIND_LABEL["ssh_key"], "SSH key");
assertStrictEqual(KIND_LABEL["ssh_password"], "SSH password");
assertStrictEqual(KIND_LABEL["vault_password"], "Vault password");
assertStrictEqual(KIND_LABEL["become_password"], "Become (sudo) password");

console.log("All credentialSlots checks passed!");
