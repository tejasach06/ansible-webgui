import { formatTimestamp } from "./time";

function assertStrictEqual(actual: unknown, expected: unknown) {
  if (actual !== expected) {
    throw new Error(`Assertion failed:\nExpected: ${JSON.stringify(expected)}\nActual:   ${JSON.stringify(actual)}`);
  }
}

assertStrictEqual(formatTimestamp(undefined), "-");
assertStrictEqual(formatTimestamp(null), "-");
assertStrictEqual(formatTimestamp(""), "-");
assertStrictEqual(formatTimestamp("invalid-date"), "invalid-date");

const formatted = formatTimestamp("2026-08-24T16:49:37.865562+00:00");
if (!formatted.includes("2026") || !formatted.includes("Aug")) {
  throw new Error(`Unexpected timestamp format: ${formatted}`);
}

console.log("All time checks passed!");
