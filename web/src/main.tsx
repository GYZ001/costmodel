import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { I18nProvider, useI18n } from "./i18n";
import type { Dataset } from "./types";
import "./styles.css";

function Root() {
  const i = useI18n();
  const [ds, setDs] = useState<Dataset | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    fetch("data/dataset.json", { cache: "no-cache" })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setDs)
      .catch((e) => setErr(String(e)));
  }, []);
  if (err) return <div className="wrap" style={{ padding: 40 }}>{i.t("app.load_error", { error: err })}</div>;
  if (!ds) return <div className="wrap muted" style={{ padding: 40 }}>{i.t("app.loading")}</div>;
  return <App ds={ds} />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <Root />
    </I18nProvider>
  </StrictMode>,
);
