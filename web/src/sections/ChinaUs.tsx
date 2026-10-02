import { useMemo, useState } from "react";
import type { Scope } from "../App";
import { countryName, fmt, minutes, sig } from "../lib";

export function ChinaUs({ ds }: Scope) {
  const L = ds.latest;
  const cn = ds.countries.CHN;
  const cnYear = cn ? Object.keys(cn.years).filter((y) => cn.years[y].wages.some((w) => w.key === "cn_wage_nonprivate")).sort().pop() : undefined;
  const cnRow = cn && cnYear ? cn.years[cnYear] : undefined;
  const cnHours = ds.cn_hours_monthly.filter(([p]) => cnYear && p.startsWith(cnYear));

  return (
    <section className="block" id="cnus">
      <h2>中美细看：口径、工时与超市价格</h2>
      <p className="sub">
        之前讨论里的中美对比，关键在三个口径：用哪种平均工资、一年按多少小时算、金价和工资是不是同一时期。
      </p>

      {cnRow && cnYear && (
        <div className="card">
          <h3>中国：同样是“平均工资”，口径差很多（{cnYear} 年）</h3>
          <div className="table-scroll">
            <table className="data">
              <thead>
                <tr>
                  <th>口径</th><th>月均（元）</th><th>折合时薪（元，按实际工时）</th><th>每小时可换黄金（克）</th>
                  <th>挣一天健康饮食要工作</th><th className="l">说明</th>
                </tr>
              </thead>
              <tbody>
                {cnRow.wages.filter((w) => w.key.startsWith("cn_")).map((w) => (
                  <tr key={w.key}>
                    <td>{w.label}</td>
                    <td>{fmt(w.monthly_lcu, 0)}</td>
                    <td>{fmt(w.hourly_lcu, 1)}</td>
                    <td>{sig(w.hourly_gold_g)}</td>
                    <td>{minutes(w.minutes_per_cohd_day)}</td>
                    <td className="l small ink2">{w.caveat}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="note">
            实际工时：国家统计局月度劳动力调查“全国企业就业人员周平均工作时间”，{cnYear} 年已公布月份
            （{cnHours.map(([p, v]) => `${Number(p.slice(5))}月 ${v}`).join("、")} 小时）的平均。
            国家统计局不单独公布 1 月数据。工时调查覆盖企业就业人员，与工资统计的覆盖面不完全一致，这是近似。
            黄金：{cnYear} 年世界银行月均金价的年平均 × 该年人民币年均汇率 = {fmt(cnRow.gold_lcu_g, 1)} 元/克。
          </p>
        </div>
      )}

      {L && L.period && (
        <div className="card">
          <h3>按最新金价算（{L.period}）</h3>
          <div className="grid3">
            <div>
              <div className="ink2 small">{L.period} 金价月均</div>
              <div style={{ fontSize: 22, fontWeight: 600 }}>{fmt(L.gold_usd_oz, 0)} 美元/盎司</div>
              <div className="small muted">= {fmt(L.gold_usd_g, 2)} 美元/克 = {fmt(L.gold_cny_g, 1)} 元/克（当月人民币月均汇率 {fmt(L.cny_per_usd, 4)}）</div>
            </div>
            <div>
              <div className="ink2 small">美国 {L.period} 私营非农平均时薪{L.us_ahe_preliminary ? "（初值）" : ""}</div>
              <div style={{ fontSize: 22, fontWeight: 600 }}>{fmt(L.us_ahe, 2)} 美元 ≈ {sig(L.us_gold_g_per_hour, 3)} 克金/小时</div>
              <div className="small muted">BLS CES0500000003；工资与金价同为 {L.period}</div>
            </div>
          </div>
          <div className="table-scroll" style={{ marginTop: 12 }}>
            <table className="data">
              <thead><tr><th>中国口径</th><th>年工资（元）</th><th>一年按多少小时</th><th>时薪（元）</th><th>按 {L.period} 金价可换黄金（克/小时）</th></tr></thead>
              <tbody>
                {L.cn.map((r) => (
                  <tr key={r.series + r.basis}>
                    <td>{r.label}（{r.wage_year}）</td>
                    <td>{fmt(r.annual, 0)}</td>
                    <td>{r.basis === "statutory" ? `${fmt(r.hours_year, 0)}（法定：250 天 × 8 小时）` : `${fmt(r.hours_year, 0)}（实际：周均工时 × 52）`}</td>
                    <td>{fmt(r.hourly, 1)}</td>
                    <td>{sig(r.gold_g_per_hour, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="note">
            中国工资一年只公布一次，这里把最近一年的年工资配上最新月份的金价，时期不一致之处已在表头标明；跨国比较的主图表均使用同一年份的工资、汇率和金价。
          </p>
        </div>
      )}

      <UsBasket ds={ds} />

      <NoChinaItems ds={ds} />
    </section>
  );
}

function UsBasket({ ds }: { ds: Scope["ds"] }) {
  const [mode, setMode] = useState<"latest" | "avg12">("latest");
  const items = useMemo(() => {
    return Object.entries(ds.us_items).map(([key, it]) => {
      const rows = it.rows.filter((r) => r.minutes !== null);
      const last = rows[rows.length - 1];
      const last12 = rows.slice(-12);
      const avg = (f: (r: (typeof rows)[number]) => number | null) => {
        const v = last12.map(f).filter((x): x is number => x !== null);
        return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
      };
      return {
        key, it, last,
        price: mode === "latest" ? last?.price : avg((r) => r.price),
        minutes: mode === "latest" ? last?.minutes : avg((r) => r.minutes),
        gold: mode === "latest" ? last?.gold_mg : avg((r) => r.gold_mg),
        span: mode === "latest" ? last?.period : `${last12[0]?.period}–${last12[last12.length - 1]?.period}`,
      };
    });
  }, [ds, mode]);
  const unitName: Record<string, string> = { kg: "千克", L: "升", dozen: "打", kWh: "千瓦时" };
  const gaps = useMemo(() => {
    const ids = new Set(Object.values(ds.us_items).map((it) => it.series_id));
    const months = ds.us_monthly.us_ahe_all_sa.map(([p]) => p);
    const since = months[Math.max(0, months.length - 24)] ?? "";
    return ds.bls_unavailable.filter((g) => g.period >= since && g.series.some((id) => ids.has(id)));
  }, [ds]);

  return (
    <div className="card">
      <h3>美国超市价格：买一份要工作多少分钟</h3>
      <div className="controls">
        <span className="seg" role="group" aria-label="时期">
          <button aria-pressed={mode === "latest"} onClick={() => setMode("latest")}>最新月份</button>
          <button aria-pressed={mode === "avg12"} onClick={() => setMode("avg12")}>最近 12 个有数据月份平均</button>
        </span>
      </div>
      <div className="table-scroll">
        <table className="data">
          <thead><tr><th>商品（BLS 平均价格）</th><th>时期</th><th>价格（美元/单位）</th><th>单位</th><th>工作时间（按当月平均时薪）</th><th>折合黄金（毫克）</th></tr></thead>
          <tbody>
            {items.map(({ key, it, price, minutes: m, gold, span }) => (
              <tr key={key}>
                <td>{it.label} <span className="muted small mono">{it.series_id}</span></td>
                <td className="small">{span}</td>
                <td>{fmt(price, 2)}</td>
                <td className="small">每{unitName[it.unit] ?? it.unit}</td>
                <td>{minutes(m)}</td>
                <td>{fmt(gold, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">
        BLS CPI 平均价格（美国城市平均，未季调）。磅、加仑已换算为千克、升。
        {gaps.length > 0 && <>最近 24 个月中 BLS 未公布数值的月份：{gaps.map((g) => `${g.period}（BLS 注：${g.note || "无说明"}）`).join("；")}。</>}
        时薪为同月 BLS 私营非农平均时薪；黄金为同月世界银行月均金价。{countryName(ds.countries.USA)}的数字仅供感受量级，商品规格与中国市场常见规格不同，不做逐项跨国对比。
      </p>
    </div>
  );
}

function NoChinaItems({ ds }: { ds: Scope["ds"] }) {
  const idx = ds.nbs_price_releases;
  return (
    <div className="card">
      <h3>为什么没有“中国超市单品价格”的逐项对比？</h3>
      <p style={{ margin: 0 }}>
        美国劳工统计局每月公布鸡蛋、牛奶、面包等商品的全国城市平均零售价（上表）。
        中国方面，本项目每次运行都会扫描国家统计局“最新发布”栏目，记录标题含“价格”的全部发布
        {idx ? `（本次覆盖 ${idx.from} 至 ${idx.to}）` : ""}，结果如下——其中没有城市食品零售单品均价：
      </p>
      {idx && (
        <table className="data" style={{ marginTop: 8 }}>
          <thead><tr><th className="l">发布类型</th><th>条数</th><th>最早</th><th>最近</th></tr></thead>
          <tbody>
            {idx.groups.map((g) => (
              <tr key={g.kind}><td className="l"><a href={g.example}>{g.kind}</a></td><td>{g.count}</td><td>{g.first}</td><td>{g.last}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="note">
        因此本页不做“中美同名商品”的逐项比价，而是用国际组织按统一规格比价的官方数据代替：世界银行的“最低成本健康饮食”（六类食物）和 ICP 分类价格水平。
        同名商品直接比价还会受规格、品质、包装差异影响，即使有数据也需谨慎解读。
      </p>
    </div>
  );
}
