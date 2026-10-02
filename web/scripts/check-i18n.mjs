// Catalog checks, run before every build:
// - every language has exactly the keys of the English catalog, with the same
//   placeholders ({name} / {name:format}) in each template;
// - every key the site's code uses (literal, or a template literal matching some key)
//   and every message key in the dataset exists in the English catalog.
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const dir = join(root, "src/i18n/locales");
const TOKEN = /\{(\w+)(?::(\w+))?\}/g;
// Placeholders as a set: a translation may use one twice.
const tokens = (s) => [...new Set([...s.matchAll(TOKEN)].map((m) => m[0]))].sort().join(" ");
const problems = [];

// --only <code>: check one language's catalog (and nothing else), e.g. while translating.
const only = process.argv.includes("--only") ? process.argv[process.argv.indexOf("--only") + 1] : null;
const en = JSON.parse(readFileSync(join(dir, "en.json"), "utf8"));
for (const file of readdirSync(dir).filter((f) => f.endsWith(".json") && (!only || f === `${only}.json`))) {
  const cat = JSON.parse(readFileSync(join(dir, file), "utf8"));
  for (const k of Object.keys(en)) {
    if (!(k in cat)) problems.push(`${file}: missing ${k}`);
    else if (typeof cat[k] !== "string" || !cat[k].length) problems.push(`${file}: empty ${k}`);
    else if (tokens(cat[k]) !== tokens(en[k])) problems.push(`${file}: ${k} placeholders ${tokens(cat[k])} ≠ ${tokens(en[k])}`);
  }
  for (const k of Object.keys(cat)) if (!(k in en)) problems.push(`${file}: extra key ${k}`);
}

if (only) {
  if (problems.length) {
    console.error(problems.join("\n"));
    process.exit(1);
  }
  console.log(`${only}: OK`);
  process.exit(0);
}

// Keys used by the code.
const walk = (d) => readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(join(d, e.name)) : [join(d, e.name)]));
const keys = Object.keys(en);
for (const f of walk(join(root, "src")).filter((f) => /\.(tsx?)$/.test(f))) {
  const src = readFileSync(f, "utf8");
  for (const m of src.matchAll(/\bi\.t\(\s*([^,)]+)/g)) {
    const arg = m[1];
    // Keys always contain a dot; other literals in the argument are conditions ("hourly").
    for (const lit of arg.matchAll(/"([a-z_]\w*(?:\.\w+)+)"/g)) if (!(lit[1] in en)) problems.push(`${f}: unknown key "${lit[1]}"`);
    for (const tpl of arg.matchAll(/`([^`]+)`/g)) {
      const re = new RegExp(`^${tpl[1].replace(/[.]/g, "\\.").replace(/\$\{[^}]+\}/g, "[\\w]+")}$`);
      if (!keys.some((k) => re.test(k))) problems.push(`${f}: no key matches \`${tpl[1]}\``);
    }
  }
}

// Message keys in the dataset.
const ds = JSON.parse(readFileSync(join(root, "public/data/dataset.json"), "utf8"));
const seen = new Set();
const visit = (o) => {
  if (Array.isArray(o)) o.forEach(visit);
  else if (o && typeof o === "object") {
    if (typeof o.k === "string" && Object.keys(o).every((x) => x === "k" || x === "p")) seen.add(o.k);
    Object.values(o).forEach(visit);
  }
};
visit(ds);
for (const k of seen) if (!(k in en)) problems.push(`dataset: unknown message key ${k}`);
for (const c of ds.checks ?? []) if (!(`check.${c.id}` in en)) problems.push(`dataset: unknown check ${c.id}`);
for (const s of ds.sources ?? []) for (const f of ["publisher", "title", "license", "use"]) if (!(`src.${s.id}.${f}` in en)) problems.push(`dataset: unknown src.${s.id}.${f}`);

if (problems.length) {
  console.error(problems.slice(0, 200).join("\n"));
  console.error(`\n${problems.length} catalog problem(s)`);
  process.exit(1);
}
console.log(`i18n catalogs OK: ${readdirSync(dir).filter((f) => f.endsWith(".json")).length} languages, ${keys.length} keys, ${seen.size} message keys in the dataset`);
