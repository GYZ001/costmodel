// Renders the dataset's language-neutral messages ({k, p}) and the site's own strings
// from a catalog of templates.  No dependencies, so scripts can run it under Node.
//
// Template tokens: "{name}" or "{name:format}".
//   numbers: num (≤6 significant digits), num4, sig2, sig3 (≤n significant digits), int,
//            d0…d6 (fixed decimals), p1 (≥1 decimal), pct0…pct3 (ratio as percent), sci1,
//            factor (×r or ÷1/r, 3 significant digits)
//   lists:   list (between statements, default), enum (enumeration), comma, sentence
//            (between full sentences: a space in most languages, nothing in Chinese or Japanese)
//   strings are inserted as they are; nested messages are rendered in the same language.
//
// Plurals: a key whose wording depends on a count has one entry per plural category of
// the language, "key#one", "key#few", …, "key#other" (Intl.PluralRules), chosen by the
// number in the parameter n.

export interface Msg {
  k: string;
  p?: Record<string, Param>;
}
export type Param = number | string | boolean | null | undefined | Msg | Param[];
export type Catalog = Record<string, string>;

export interface Ctx {
  cat: Catalog;
  fallback: Catalog;
  /** BCP 47 tag for Intl formatting, e.g. "zh-CN", "ar-u-nu-latn". */
  locale: string;
}

const TOKEN = /\{(\w+)(?::(\w+))?\}/g;
const nf = new Map<string, Intl.NumberFormat>();

function numberFormat(locale: string, key: string, opts: Intl.NumberFormatOptions): Intl.NumberFormat {
  const k = `${locale}|${key}`;
  let f = nf.get(k);
  if (!f) {
    f = new Intl.NumberFormat(locale, opts);
    nf.set(k, f);
  }
  return f;
}

export function formatNumber(x: number, fmt: string, locale: string): string {
  if (!Number.isFinite(x)) return "—";
  let m: RegExpMatchArray | null;
  if (fmt === "int") return numberFormat(locale, fmt, { maximumFractionDigits: 0 }).format(x);
  if ((m = fmt.match(/^d(\d)$/))) {
    const d = Number(m[1]);
    return numberFormat(locale, fmt, { minimumFractionDigits: d, maximumFractionDigits: d }).format(x);
  }
  if ((m = fmt.match(/^pct(\d)$/))) {
    const d = Number(m[1]);
    return numberFormat(locale, fmt, { style: "percent", minimumFractionDigits: d, maximumFractionDigits: d }).format(x);
  }
  if ((m = fmt.match(/^sig(\d)$/))) return sig(x, Number(m[1]), locale);
  switch (fmt) {
    case "p1":
      return Math.round(x * 10) / 10 === x ? formatNumber(x, "d1", locale) : formatNumber(x, "num", locale);
    case "sci1":
      return x.toExponential(1).replace("e+", "e");
    case "factor":
      return x >= 1 ? `×${sig(x, 3, locale)}` : `÷${sig(1 / x, 3, locale)}`;
    case "num4":
      return sig(x, 4, locale);
    default:
      return sig(x, 6, locale);
  }
}

function sig(x: number, n: number, locale: string): string {
  return numberFormat(locale, `sig${n}`, { maximumSignificantDigits: n }).format(x);
}

export function join(items: string[], kind: string, ctx: Ctx): string {
  const sep = ctx.cat[`_sep.${kind}`] ?? ctx.fallback[`_sep.${kind}`] ?? "; ";
  return items.filter((x) => x).join(sep);
}

export function render(part: Param, ctx: Ctx, fmt?: string): string {
  if (part === null || part === undefined || part === "") return "";
  if (typeof part === "string") return part;
  if (typeof part === "number") return formatNumber(part, fmt ?? "num", ctx.locale);
  if (typeof part === "boolean") return String(part);
  if (Array.isArray(part)) return join(part.map((p) => render(p, ctx)), fmt ?? "list", ctx);
  return template(part.k, part.p ?? {}, ctx);
}

const pr = new Map<string, Intl.PluralRules>();

/** Plural rules matching a number format, so that the form agrees with the digits shown
 *  ("1 day", "1.0 days"). */
function pluralFormat(fmt: string): Intl.PluralRulesOptions {
  let m: RegExpMatchArray | null;
  if (fmt === "int") return { maximumFractionDigits: 0 };
  if ((m = fmt.match(/^d(\d)$/))) return { minimumFractionDigits: Number(m[1]), maximumFractionDigits: Number(m[1]) };
  if ((m = fmt.match(/^sig(\d)$/))) return { maximumSignificantDigits: Number(m[1]) };
  if (fmt === "num4") return { maximumSignificantDigits: 4 };
  return { maximumSignificantDigits: 6 };
}

/** The plural category of n in the locale ("one", "few", "other", …), as n is shown in fmt. */
export function pluralCategory(n: number, locale: string, fmt = "num"): string {
  const k = `${locale}|${fmt}`;
  let r = pr.get(k);
  if (!r) {
    r = new Intl.PluralRules(locale, pluralFormat(fmt));
    pr.set(k, r);
  }
  return r.select(n);
}

function lookup(cat: Catalog, key: string, params: Record<string, Param>, locale: string): string | undefined {
  if (key in cat) return cat[key];
  const other = cat[`${key}#other`];
  if (other === undefined) return undefined;
  const n = params.n;
  if (typeof n !== "number") return other;
  const fmt = other.match(/\{n:(\w+)\}/)?.[1] ?? "num";
  return cat[`${key}#${pluralCategory(n, locale, fmt)}`] ?? other;
}

export function template(key: string, params: Record<string, Param>, ctx: Ctx): string {
  const tpl = lookup(ctx.cat, key, params, ctx.locale) ?? lookup(ctx.fallback, key, params, "en");
  if (tpl === undefined) return key;
  return tpl.replace(TOKEN, (whole, name: string, fmt?: string) => (name in params ? render(params[name], ctx, fmt) : whole));
}

/** Placeholder names (with formats) in a template, for catalog consistency checks. */
export function tokens(tpl: string): string[] {
  return [...tpl.matchAll(TOKEN)].map((m) => m[0]).sort();
}
