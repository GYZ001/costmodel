import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import type { Dataset } from "./types";
import "./styles.css";

function Root() {
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
  if (err) return <div className="wrap" style={{ padding: 40 }}>数据加载失败：{err}</div>;
  if (!ds) return <div className="wrap muted" style={{ padding: 40 }}>正在加载官方数据…</div>;
  return <App ds={ds} />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
