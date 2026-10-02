// Languages of the site: at least one main language of every G20 member country.
// code = catalog file name (locales/<code>.json); locale = tag for Intl formatting.
export interface Lang {
  code: string;
  name: string; // the language's own name
  locale: string;
  dir: "ltr" | "rtl";
}

export const LANGS: Lang[] = [
  { code: "en", name: "English", locale: "en", dir: "ltr" },
  { code: "zh-CN", name: "简体中文", locale: "zh-CN", dir: "ltr" },
  { code: "es", name: "Español", locale: "es", dir: "ltr" },
  { code: "pt-BR", name: "Português (Brasil)", locale: "pt-BR", dir: "ltr" },
  { code: "fr", name: "Français", locale: "fr", dir: "ltr" },
  { code: "de", name: "Deutsch", locale: "de", dir: "ltr" },
  { code: "it", name: "Italiano", locale: "it", dir: "ltr" },
  { code: "ru", name: "Русский", locale: "ru", dir: "ltr" },
  { code: "tr", name: "Türkçe", locale: "tr", dir: "ltr" },
  { code: "ar", name: "العربية", locale: "ar-u-nu-latn", dir: "rtl" },
  { code: "hi", name: "हिन्दी", locale: "hi", dir: "ltr" },
  { code: "id", name: "Bahasa Indonesia", locale: "id", dir: "ltr" },
  { code: "ja", name: "日本語", locale: "ja", dir: "ltr" },
  { code: "ko", name: "한국어", locale: "ko", dir: "ltr" },
];

export const DEFAULT_LANG = "en";

/** The site language for a browser language tag (exact, then by base language). */
export function matchLang(tag: string): string | null {
  const t = tag.toLowerCase();
  const exact = LANGS.find((l) => l.code.toLowerCase() === t);
  if (exact) return exact.code;
  const base = t.split("-")[0];
  return LANGS.find((l) => l.code.toLowerCase().split("-")[0] === base)?.code ?? null;
}
