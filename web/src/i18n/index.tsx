import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import en from "./locales/en.json";
import { DEFAULT_LANG, LANGS, matchLang, type Lang } from "./langs";
import { formatNumber, join, render, template, type Catalog, type Ctx, type Param } from "./render";

// Catalogs other than the fallback (English) load on demand.
const loaders = import.meta.glob<Catalog>(["./locales/*.json", "!./locales/en.json"], { import: "default" });

export interface I18n {
  lang: Lang;
  setLang: (code: string) => void;
  /** The site's own text: t("key", {param}) */
  t: (key: string, params?: Record<string, Param>) => string;
  /** A message from the dataset ({k, p}), a list of them, or a verbatim string. */
  r: (part: Param) => string;
  /** A number in one of the catalog formats (num, int, d2, pct2, factor, …). */
  n: (x: number | null | undefined, fmt?: string) => string;
  /** Strings joined with the language's separator: list (between statements), enum, comma. */
  j: (items: string[], kind?: "list" | "enum" | "comma") => string;
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
    const code = tag ? matchLang(tag) : null;
    if (code) return code;
  }
  return DEFAULT_LANG;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [code, setCode] = useState(initialLang);
  const [cats, setCats] = useState<Record<string, Catalog>>({ en: en as Catalog });
  const lang = LANGS.find((l) => l.code === code) ?? LANGS[0];

  useEffect(() => {
    if (cats[code]) return;
    const load = loaders[`./locales/${code}.json`];
    if (!load) return;
    load().then((cat) => setCats((c) => ({ ...c, [code]: cat })));
  }, [code, cats]);

  useEffect(() => {
    document.documentElement.lang = lang.code;
    document.documentElement.dir = lang.dir;
    try {
      localStorage.setItem("lang", lang.code);
    } catch {
      /* private mode: the choice is not remembered */
    }
    const url = new URL(location.href);
    url.searchParams.set("lang", lang.code);
    history.replaceState(null, "", url);
  }, [lang]);

  const value = useMemo<I18n>(() => {
    const ctx: Ctx = { cat: cats[code] ?? {}, fallback: en as Catalog, locale: lang.locale };
    return {
      lang,
      setLang: setCode,
      t: (key, params) => template(key, params ?? {}, ctx),
      r: (part) => render(part, ctx),
      n: (x, fmt = "num") => (x === null || x === undefined ? "—" : formatNumber(x, fmt, lang.locale)),
      j: (items, kind = "list") => join(items, kind, ctx),
      ctx,
    };
  }, [cats, code, lang]);

  useEffect(() => {
    document.title = value.t("app.title");
  }, [value]);

  // Until the chosen catalog has loaded, English (the fallback) is shown.
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(I18nContext);
  if (!v) throw new Error("useI18n outside I18nProvider");
  return v;
}
