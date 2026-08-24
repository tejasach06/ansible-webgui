import { formatValue, humanKey } from "./KeyValueTable";

function assertStrictEqual(actual: unknown, expected: unknown) {
  if (actual !== expected) {
    throw new Error(`Assertion failed:\nExpected: ${JSON.stringify(expected)}\nActual:   ${JSON.stringify(actual)}`);
  }
}

assertStrictEqual(formatValue({ a: 1, b: { c: true } }), "A: 1\nB:\n  C: Yes");
assertStrictEqual(formatValue([1, 2]), "1, 2");
assertStrictEqual(formatValue([]), "-");
assertStrictEqual(formatValue(false), "No");
assertStrictEqual(formatValue(true), "Yes");
assertStrictEqual(formatValue(null), "-");
assertStrictEqual(formatValue(undefined), "-");
assertStrictEqual(formatValue(""), "-");
assertStrictEqual(humanKey("skip_tags"), "Skip tags");
assertStrictEqual(humanKey("git_sha"), "Git sha");
assertStrictEqual(humanKey("already spaced"), "Already spaced");

console.log("All KeyValueTable checks passed!");
