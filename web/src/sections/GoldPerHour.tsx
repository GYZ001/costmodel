import { useMemo } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { rankingHeight, rankingOption, type RankItem } from "../charts";
import { countryName, money, primaryWage, rowFor, sig, typicalWage, useThemeVersion } from "../lib";

export function useRows(scope: Scope) {
  const { ds, yearMode, group } = scope;
  return useMemo(() => {
    return Object.entries(ds.countries)
      .filter(([iso, c]) => group === "all" || c.g20 || scope.picks.includes(iso))
      .map(([iso, c]) => {
        const r = rowFor(c, yearMode);
        return r ? { iso, c, year: r.year, row: r.row } : null;
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);
  }, [ds, yearMode, group, scope.picks]);
}

export function GoldPerHour(scope: Scope) {
  const theme = useThemeVersion();
  const rows = useRows(scope);
  const items: RankItem[] = useMemo(
    () =>
      rows.flatMap(({ iso, c, year, row }) => {
        const w = primaryWage(row);
        if (!w?.hourly_gold_g) return [];
        const t = typicalWage(row);
        return [{
          id: iso,
          name: `${countryName(c)}${scope.yearMode === "latest" ? `（${year}）` : ""}`,
          value: w.hourly_gold_g,
          secondary: t?.hourly_gold_g ?? null,
          highlight: scope.picks.includes(iso),
          tip: [
            `${w.label}：${money(w.hourly_lcu, c.currency)}/小时`,
            `当地金价：${money(row.gold_lcu_g, c.currency)}/克（${year} 年均）`,
            w.source,
          ],
        }];
      }),
    [rows, scope.picks, scope.yearMode],
  );
  const option = useMemo(
    () => rankingOption({
      items,
      valueName: "平均时薪可换黄金",
      secondaryName: "中位时薪可换黄金",
      format: (v) => `${sig(v, 2)} 克`,
    }),
    [items, theme],
  );

  return (
    <section className="block" id="gold">
      <h2>① 劳动 → 黄金：每小时工资能换多少克黄金</h2>
      <p className="sub">
        时薪 ÷（该年国际金价 × 该年平均汇率）。这一步等价于把时薪按市场汇率换成美元，再除以美元金价。
        横轴为对数刻度，差距跨度很大。
      </p>
      <div className="card">
        <div className="legend">
          <span><span className="sw" style={{ background: "var(--accent)" }} />重点对比的经济体（平均时薪）</span>
          <span><span className="sw" style={{ background: "var(--deemph)" }} />其他经济体（平均时薪）</span>
          <span><span className="sw" style={{ background: "var(--s2)", borderRadius: "50%" }} />中位时薪（有数据时）</span>
        </div>
        <Chart option={option} height={rankingHeight(items.length)} ariaLabel="各经济体每小时工资可换黄金克数排名" />
        <p className="note">
          工资：国际劳工组织 ILOSTAT 的雇员平均/中位时薪；只有月薪的经济体用“月薪 ÷ 每周实际工时 × 12/52”折算；中国用国家统计局城镇非私营单位平均工资与企业周平均工时折算（私营单位与农民工见“中美细看”）。
          金价：世界银行 Pink Sheet 月均价的年平均；汇率：世界银行 WDI 年均官方汇率。
        </p>
        <DataTable items={items} />
      </div>
    </section>
  );
}

function DataTable({ items }: { items: RankItem[] }) {
  const sorted = [...items].sort((a, b) => b.value - a.value);
  return (
    <details>
      <summary>查看数据表（{items.length} 个经济体）</summary>
      <div className="table-scroll">
        <table className="data">
          <thead>
            <tr><th>经济体</th><th>平均时薪 → 克金</th><th>中位时薪 → 克金</th><th className="l">说明</th></tr>
          </thead>
          <tbody>
            {sorted.map((i) => (
              <tr key={i.id}>
                <td>{i.name}</td>
                <td>{sig(i.value)}</td>
                <td>{sig(i.secondary ?? null)}</td>
                <td className="l small ink2">{i.tip.join("；")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
