import { runSummary } from "./runSummary";
import type { JobDetail } from "./types";

function assertStrictEqual(actual: unknown, expected: unknown) {
  if (actual !== expected) {
    throw new Error(`Assertion failed:\nExpected: ${JSON.stringify(expected)}\nActual:   ${JSON.stringify(actual)}`);
  }
}

const fullJob: JobDetail = {
  id: 1,
  playbook_id: 2,
  inventory_id: 3,
  mode: "live",
  status: "pending_approval",
  requested_by: 4,
  params_snapshot: { limit: "web", tags: "deploy", become: true, become_user: "root" },
  context: {
    playbook_rel_path: "playbooks/deploy.yml",
    inventory_rel_path: "inventories/prod.yml",
    credentials: [],
  },
};

assertStrictEqual(
  runSummary(fullJob),
  "Runs playbooks/deploy.yml against web in inventories/prod.yml in live mode, changes are applied. Escalates privileges as root. Limited to tags: deploy."
);

const emptyJob: JobDetail = {
  id: 2,
  playbook_id: 2,
  inventory_id: 0,
  mode: "check",
  status: "pending_approval",
  requested_by: 4,
  params_snapshot: {},
  context: {
    playbook_name: "Deploy",
    credentials: [],
  },
};

assertStrictEqual(
  runSummary(emptyJob),
  "Runs Deploy against all hosts in check mode, nothing is changed."
);

assertStrictEqual(runSummary(undefined), "");

console.log("All runSummary checks passed!");
