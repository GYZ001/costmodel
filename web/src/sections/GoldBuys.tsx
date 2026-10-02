import { useMemo, useState } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { rankingHeight, rankingOption, type RankItem } from "../charts";
import { countryName, fmt, money, sig, useThemeVersion } from "../lib";
import { useRows } from "./GoldPerHour";

type Measure = "diet" | "consumption";

export function GoldBuys(scope: Scope) {
  const theme = useThemeVersion();
  const rows = useRows(scope);
  const [m, setM] = useState<Measure>("diet");
  const items: RankItem[] = useMemo(
    () =>
      rows.flatMap(({ iso, c, year, row }) => {
        const v = m === "diet" ? row.cohd_days_per_g : row.gold_usdeq_g;
        if (!v) return [];
        const tip = m === "diet"
          ? [`当地金价 ${money(row.gold_lcu_g, c.currency)}/克`, `一人一天最低成本健康饮食 ${money(row.cohd.total, c.currency)}（${year}）`]
          : [`居民消费价格水平 = 美国的 ${fmt(row.pli_hfce, 2)} 倍（${year}）`, `1 克黄金值 ${fmt(row.gold_usd_g, 1)} 美元`];
        return [{
          id: iso,
          name: countryName(c),
          value: v,
          highlight: scope.picks.includes(iso),
          tip,
        }];
      }),
    [rows, m, scope.picks],
  );
  const usRow = scope.ds.countries.USA && rows.find((r) => r.iso === "USA");
  const option = useMemo(
    () => rankingOption({
      items,
      valueName: m === "diet" ? "1 克黄金可买健康饮食" : "1 克黄金的购买力（美国物价下的等值美元）",
      format: (v) => (m === "diet" ? `${sig(v, 2)} 天` : `$${fmt(v, 0)}`),
      refLine: m === "consumption" && usRow ? { value: usRow.row.gold_usd_g, label: "美国" } : undefined,
    }),
    [items, m, theme],
  );

  return (
    <section className="block" id="buys">
      <h2>② 黄金 → 商品：一克黄金在当地能买多少（{scope.year} 年）</h2>
      <p className="sub">
        本页各地金价按“美元金价 × 汇率”计算，换成美元都一样；但同一克黄金换成本币后，在物价低的地方能买到更多东西。
        这一步的差异，就是各国物价水平的差异。
      </p>
      <div className="card">
        <div className="controls">
          <span className="seg" role="group" aria-label="衡量方式">
            <button aria-pressed={m === "diet"} onClick={() => setM("diet")}>能买几天健康饮食（食物）</button>
            <button aria-pressed={m === "consumption"} onClick={() => setM("consumption")}>相当于在美国花多少美元（全部居民消费）</button>
          </span>
        </div>
        <div className="legend">
          <span><span className="sw" style={{ background: "var(--accent)" }} />重点对比的经济体</span>
          <span><span className="sw" style={{ background: "var(--deemph)" }} />其他经济体</span>
        </div>
        <Chart option={option} height={rankingHeight(items.length)} ariaLabel="一克黄金在各经济体的购买力" />
        <p className="note">
          {m === "diet"
            ? "健康饮食：世界银行“Food Prices for Nutrition”数据库中的一人一天最低成本健康饮食（本币，当年价格）。它只覆盖食物，并且取的是各类食物中最便宜的可得选项，不是普通家庭的实际菜篮子。"
            : "等值美元 = 1 克黄金的美元价格 ÷ 该国居民消费价格水平（购买力平价 ÷ 市场汇率，世界银行 WDI）。覆盖全部居民消费（含住房、服务），美国为基准。"}
        </p>
        <details>
          <summary>查看数据表（{items.length} 个经济体）</summary>
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th>经济体</th><th>{m === "diet" ? "1 克金 = 天健康饮食" : "1 克金 = 美国物价下的美元"}</th><th className="l">计算依据</th></tr></thead>
              <tbody>
                {[...items].sort((a, b) => b.value - a.value).map((i) => (
                  <tr key={i.id}><td>{i.name}</td><td>{m === "diet" ? sig(i.value) : fmt(i.value, 1)}</td><td className="l small ink2">{i.tip.join("；")}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </section>
  );
}
