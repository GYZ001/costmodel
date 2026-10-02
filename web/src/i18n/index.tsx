import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import en from "./locales/en.json";
import { DEFAULT_LANG, LANGS, matchLang, type Lang } from "./langs";
import { formatNumber, join, render, template, type Catalog, type Ctx, type Param } from "./render";

// Catalogs other than the fallback (English) load on demand.
const loaders = import.meta.glob<Catalog>(["./locales/*.json", "!./locales/en.json"], { import: "default" });
const loaderOf = (code: string) => loaders[`./locales/${code}.json`];

/** The languages offered: those whose catalog exists. */
export const AVAILABLE: Lang[] = LANGS.filter((l) => l.code === DEFAULT_LANG || loaderOf(l.code));

export interface I18n {
  lang: Lang;
  langs: Lang[];
  setLang: (code: string) => void;
  /** The site's own text: t("key", {param}) */
  t: (key: string, params?: Record<string, Param>) => string;
  /** A message from the dataset ({k, p}), a list of them, or a verbatim string. */
  r: (part: Param) => string;
  /** A number in one of the catalog formats (num, int, d2, pct2, factor, …). */
  n: (x: number | null | undefined, fmt?: string) => string;
  /** Strings joined with the language's separator: list (between statements), enum,
   *  comma, sentence (between full sentences). */
  j: (items: string[], kind?: "list" | "enum" | "comma" | "sentence") => string;
  ctx: Ctx;
}

const I18nContext = createContext<I18n | null>(null);

function storedLang(): string | null {
  try {
    return localStorage.getItem("lang");
  } catch {
    return null;
  }
}

function initialLang(): string {
  const fromUrl = new URLSearchParams(location.search).get("lang");
  for (const tag of [fromUrl, storedLang(), ...(navigator.languages ?? [navigator.language])]) {
    const code = tag ? matchLang(tag, AVAILABLE) : null;
    if (code) return code;
  }
  return DEFAULT_LANG;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  // code: the language the reader chose; shown: the language whose catalog is on the
  // page (English until the chosen catalog has loaded, so text, direction and number
  // formats always come from one catalog).  Only a language actually shown is
  // remembered; a catalog that fails to load leaves the page as it was, and choosing
  // the language again retries.
  const [code, setCode] = useState(initialLang);
  const [attempt, setAttempt] = useState(0);
  const [cats, setCats] = useState<Record<string, Catalog>>({ en: en as Catalog });
  const [shown, setShown] = useState(DEFAULT_LANG);
  const lang = AVAILABLE.find((l) => l.code === shown) ?? AVAILABLE[0];

  useEffect(() => {
    if (cats[code]) {
      setShown(code);
      return;
    }
    const load = loaderOf(code);
    if (!load) return;
    let live = true;
    load()
      .then((cat) => live && setCats((c) => ({ ...c, [code]: cat })))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [code, cats, attempt]);

  useEffect(() => {
    document.documentElement.lang = lang.code;
    document.documentElement.dir = lang.dir;
  }, [lang]);

  useEffect(() => {
    if (shown !== code) return; // not yet (or not) shown: the stored choice stays as it is
    try {
      localStorage.setItem("lang", code);
    } catch {
      /* private mode: the choice is not remembered */
    }
    const url = new URL(location.href);
    url.searchParams.set("lang", code);
    history.replaceState(null, "", url);
  }, [shown, code]);

  const value = useMemo<I18n>(() => {
    const ctx: Ctx = { cat: cats[shown] ?? {}, fallback: en as Catalog, locale: lang.locale };
    return {
      lang,
      langs: AVAILABLE,
      setLang: (c: string) => {
        setCode(c);
        setAttempt((n) => n + 1);
      },
      t: (key, params) => template(key, params ?? {}, ctx),
      r: (part) => render(part, ctx),
      n: (x, fmt = "num") => (x === null || x === undefined ? "—" : formatNumber(x, fmt, lang.locale)),
      j: (items, kind = "list") => join(items, kind, ctx),
      ctx,
    };
  }, [cats, shown, lang]);

  useEffect(() => {
    document.title = value.t("app.title");
    document.querySelector('meta[name="description"]')?.setAttribute("content", value.t("app.description"));
  }, [value]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(I18nContext);
  if (!v) throw new Error("useI18n outside I18nProvider");
  return v;
}
