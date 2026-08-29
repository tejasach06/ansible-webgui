import assert from "node:assert";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const cssPath = path.resolve(__dirname, "../src/index.css");
const css = fs.readFileSync(cssPath, "utf-8");

function parseTokens(cssText, selector) {
  const regex = new RegExp(`${selector.replace(".", "\\.")}\\s*\\{([^}]+)\\}`, "s");
  const match = cssText.match(regex);
  if (!match) throw new Error(`Selector not found: ${selector}`);
  const tokens = {};
  const lines = match[1].split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("--")) {
      const [k, v] = trimmed.replace(";", "").split(":").map(s => s.trim());
      tokens[k] = v.split(/\s+/).map(Number);
    }
  }
  return tokens;
}

const rootTokens = parseTokens(css, ":root");
const darkTokens = parseTokens(css, ".dark");

// Assert identical variable names
const rootKeys = Object.keys(rootTokens).sort();
const darkKeys = Object.keys(darkTokens).sort();
assert.deepStrictEqual(rootKeys, darkKeys, "Variable names between :root and .dark must be identical");

function relativeLuminance([r8, g8, b8]) {
  const [r, g, b] = [r8, g8, b8].map(v => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(rgb1, rgb2) {
  const l1 = relativeLuminance(rgb1);
  const l2 = relativeLuminance(rgb2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

const checks = [
  { name: "--fg-muted on --surface", fg: "--fg-muted", bg: "--surface", min: 4.5 },
  { name: "--fg-subtle on --surface", fg: "--fg-subtle", bg: "--surface", min: 4.5 },
  { name: "--accent-solid-fg on --accent-solid", fg: "--accent-solid-fg", bg: "--accent-solid", min: 4.5 },
  { name: "--warn on --surface", fg: "--warn", bg: "--surface", min: 4.5 },
  { name: "--danger on --surface", fg: "--danger", bg: "--surface", min: 4.5 },
  { name: "--fg on --surface", fg: "--fg", bg: "--surface", min: 7.0 },
];

for (const theme of [{ name: "light", tokens: rootTokens }, { name: "dark", tokens: darkTokens }]) {
  for (const check of checks) {
    const fg = theme.tokens[check.fg];
    const bg = theme.tokens[check.bg];
    assert(fg, `Missing token ${check.fg} in ${theme.name}`);
    assert(bg, `Missing token ${check.bg} in ${theme.name}`);
    const ratio = contrastRatio(fg, bg);
    assert(
      ratio >= check.min,
      `Contrast failure in ${theme.name} for ${check.name}: ${ratio.toFixed(2)}:1 (minimum required: ${check.min}:1)`
    );
  }
}

console.log("Contrast checks passed: all semantic tokens meet WCAG contrast requirements.");
