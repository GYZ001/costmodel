// Renders the dataset's language-neutral messages ({k, p}) and the site's own strings
// from a catalog of templates.  No dependencies, so scripts can run it under Node.
//
// Template tokens: "{name}" or "{name:format}".
//   numbers: num (≤6 significant digits), num4, sig2, sig3 (≤n significant digits), int,
//            d0…d6 (fixed decimals), p1 (≥1 decimal), pct0…pct3 (ratio as percent), sci1,
//            factor (×r or ÷1/r, 3 significant digits)
//   lists:   list (sentence separator, default), enum (enumeration), comma
//   strings are inserted as they are; nested messages are rendered in the same language.

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

// A part ending with a full-width full stop (e.g. a quoted Chinese sentence) takes no
// sentence separator after it.
const SENTENCE_END = /。$/;

export function join(items: string[], kind: string, ctx: Ctx): string {
  const sep = ctx.cat[`_sep.${kind}`] ?? ctx.fallback[`_sep.${kind}`] ?? "; ";
  let out = "";
  for (const x of items) {
    if (!x) continue;
    out += !out || (kind === "list" && SENTENCE_END.test(out)) ? x : sep + x;
  }
  return out;
}

export function render(part: Param, ctx: Ctx, fmt?: string): string {
  if (part === null || part === undefined || part === "") return "";
  if (typeof part === "string") return part;
  if (typeof part === "number") return formatNumber(part, fmt ?? "num", ctx.locale);
  if (typeof part === "boolean") return String(part);
  if (Array.isArray(part)) return join(part.map((p) => render(p, ctx)), fmt ?? "list", ctx);
  return template(part.k, part.p ?? {}, ctx);
}

export function template(key: string, params: Record<string, Param>, ctx: Ctx): string {
  const tpl = ctx.cat[key] ?? ctx.fallback[key];
  if (tpl === undefined) return key;
  return tpl.replace(TOKEN, (whole, name: string, fmt?: string) => (name in params ? render(params[name], ctx, fmt) : whole));
}

/** Placeholder names (with formats) in a template, for catalog consistency checks. */
export function tokens(tpl: string): string[] {
  return [...tpl.matchAll(TOKEN)].map((m) => m[0]).sort();
}
