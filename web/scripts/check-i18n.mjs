// Catalog checks, run before every build:
// - every catalog belongs to a language listed in src/i18n/langs.ts, and (with
//   --require-all, as in the build) every listed language has a catalog;
// - every language has exactly the keys of the English catalog, with the same
//   placeholders ({name} / {name:format}) in each template;
// - a key whose wording depends on a count ("key#one", "key#other", …) has, in each
//   language, exactly the plural categories of that language (Intl.PluralRules);
// - every key the site's code uses (literal, or a template literal matching some key)
//   and every message key in the dataset exists in the English catalog.
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const dir = join(root, "src/i18n/locales");
const TOKEN = /\{(\w+)(?::(\w+))?\}/g;
const tokenSet = (s) => new Set([...s.matchAll(TOKEN)].map((m) => m[0]));
// Placeholders as a set: a translation may use one twice.
const tokens = (s) => [...tokenSet(s)].sort().join(" ");
const problems = [];

const args = process.argv.slice(2);
// --only <code>: check one language's catalog (and nothing else), e.g. while translating.
const only = args.includes("--only") ? args[args.indexOf("--only") + 1] : null;
const requireAll = args.includes("--require-all");

// The site's languages: code (catalog file name) and locale (for plural rules).
const langsSrc = readFileSync(join(root, "src/i18n/langs.ts"), "utf8");
const LANGS = [...langsSrc.matchAll(/\{\s*code:\s*"([^"]+)",[^}]*locale:\s*"([^"]+)"/g)].map((m) => ({ code: m[1], locale: m[2] }));
const localeOf = Object.fromEntries(LANGS.map((l) => [l.code, l.locale]));
const files = readdirSync(dir).filter((f) => f.endsWith(".json"));
const codes = files.map((f) => f.replace(/\.json$/, ""));
for (const c of codes) if (!localeOf[c]) problems.push(`locales/${c}.json: language not listed in langs.ts`);
if (requireAll) for (const l of LANGS) if (!codes.includes(l.code)) problems.push(`langs.ts: ${l.code} has no catalog`);

const en = JSON.parse(readFileSync(join(dir, "en.json"), "utf8"));
const plain = Object.keys(en).filter((k) => !k.includes("#"));
const families = [...new Set(Object.keys(en).filter((k) => k.includes("#")).map((k) => k.split("#")[0]))];
for (const f of families) if (!(`${f}#other` in en)) problems.push(`en.json: ${f} has plural forms but no #other`);
const known = new Set([...plain, ...families]); // keys the code and the dataset may name

for (const file of files.filter((f) => !only || f === `${only}.json`)) {
  const code = file.replace(/\.json$/, "");
  const cat = JSON.parse(readFileSync(join(dir, file), "utf8"));
  // Separators may be empty (no space between sentences in Chinese or Japanese); text may not.
  const ok = (k) => typeof cat[k] === "string" && (cat[k].length > 0 || k.startsWith("_sep."));
  for (const k of plain) {
    if (!(k in cat)) problems.push(`${file}: missing ${k}`);
    else if (!ok(k)) problems.push(`${file}: empty ${k}`);
    else if (tokens(cat[k]) !== tokens(en[k])) problems.push(`${file}: ${k} placeholders ${tokens(cat[k])} ≠ ${tokens(en[k])}`);
  }
  const forms = localeOf[code] ? new Intl.PluralRules(localeOf[code]).resolvedOptions().pluralCategories : ["other"];
  const allowed = new Set(plain);
  for (const f of families) {
    const other = tokenSet(en[`${f}#other`] ?? "");
    for (const form of forms) {
      const k = `${f}#${form}`;
      allowed.add(k);
      if (!(k in cat)) problems.push(`${file}: missing ${k} (plural forms of ${localeOf[code]}: ${forms.join(", ")})`);
      else if (!ok(k)) problems.push(`${file}: empty ${k}`);
      else if (form === "other" ? tokens(cat[k]) !== tokens(en[`${f}#other`]) : [...tokenSet(cat[k])].some((t) => !other.has(t)))
        problems.push(`${file}: ${k} placeholders ${tokens(cat[k])} do not match ${[...other].sort().join(" ")}`);
    }
  }
  for (const k of Object.keys(cat)) if (!allowed.has(k)) problems.push(`${file}: extra key ${k}`);
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
for (const f of walk(join(root, "src")).filter((f) => /\.(tsx?)$/.test(f))) {
  const src = readFileSync(f, "utf8");
  for (const m of src.matchAll(/\bi\.t\(\s*([^,)]+)/g)) {
    const arg = m[1];
    // Keys always contain a dot; other literals in the argument are conditions ("hourly").
    for (const lit of arg.matchAll(/"([a-z_]\w*(?:\.\w+)+)"/g)) if (!known.has(lit[1])) problems.push(`${f}: unknown key "${lit[1]}"`);
    for (const tpl of arg.matchAll(/`([^`]+)`/g)) {
      const re = new RegExp(`^${tpl[1].replace(/[.]/g, "\\.").replace(/\$\{[^}]+\}/g, "[\\w]+")}$`);
      if (![...known].some((k) => re.test(k))) problems.push(`${f}: no key matches \`${tpl[1]}\``);
    }
  }
}

// Message keys the pipeline can emit: M("key", …) and M(f"key_{…}", …).
const pipelineDir = join(root, "../pipeline/wagegold");
for (const f of walk(pipelineDir).filter((f) => f.endsWith(".py"))) {
  const src = readFileSync(f, "utf8");
  for (const m of src.matchAll(/\bM\(\s*(f?)"([^"]+)"/g)) {
    if (!m[1]) {
      if (!known.has(m[2])) problems.push(`${f}: unknown message key "${m[2]}"`);
    } else {
      const re = new RegExp(`^${m[2].replace(/[.]/g, "\\.").replace(/\{[^}]+\}/g, "\\w+")}$`);
      if (![...known].some((k) => re.test(k))) problems.push(`${f}: no key matches f"${m[2]}"`);
    }
  }
}

// The static page shell (shown before the script runs, and to link previews) is the
// English catalog's title and description.
const shell = readFileSync(join(root, "index.html"), "utf8");
const unescape = (x) => x.replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">");
const shellTitle = unescape(shell.match(/<title>([^<]*)<\/title>/)?.[1] ?? "");
const shellDesc = unescape(shell.match(/<meta name="description" content="([^"]*)"/)?.[1] ?? "");
if (shellTitle !== en["app.title"]) problems.push(`index.html: <title> differs from en app.title`);
if (shellDesc !== en["app.description"]) problems.push(`index.html: description differs from en app.description`);
if (!/<html lang="en"/.test(shell)) problems.push(`index.html: <html lang> must be "en" (the catalog the shell is written from)`);

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
for (const k of seen) if (!known.has(k)) problems.push(`dataset: unknown message key ${k}`);
for (const c of ds.checks ?? []) if (!known.has(`check.${c.id}`)) problems.push(`dataset: unknown check ${c.id}`);
for (const s of ds.sources ?? []) for (const f of ["publisher", "title", "license", "use"]) if (!known.has(`src.${s.id}.${f}`)) problems.push(`dataset: unknown src.${s.id}.${f}`);

if (problems.length) {
  console.error(problems.slice(0, 200).join("\n"));
  console.error(`\n${problems.length} catalog problem(s)`);
  process.exit(1);
}
console.log(`i18n catalogs OK: ${files.length} languages, ${plain.length} keys + ${families.length} plural keys, ${seen.size} message keys in the dataset`);
