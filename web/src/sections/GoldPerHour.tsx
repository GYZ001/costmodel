import { useMemo } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { rankingHeight, rankingOption, type RankItem } from "../charts";
import { countryName, fmt, fxNote, money, otherWages, primaryWage, rowFor, sig, typicalWage, useThemeVersion, wageLabel, wageNotes } from "../lib";

export function useRows(scope: Scope) {
  const { ds, year, group } = scope;
  return useMemo(() => {
    return Object.entries(ds.countries)
      .filter(([iso, c]) => group === "all" || c.g20 || scope.picks.includes(iso))
      .map(([iso, c]) => {
        const r = rowFor(c, year);
        return r ? { iso, c, year: r.year, row: r.row } : null;
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);
  }, [ds, year, group, scope.picks]);
}

export function GoldPerHour(scope: Scope) {
  const theme = useThemeVersion();
  const rows = useRows(scope);
  const items: RankItem[] = useMemo(
    () =>
      rows.flatMap(({ iso, c, year, row }) => {
        const hourly = scope.view === "hourly";
        const w = primaryWage(row, scope.view);
        const v = hourly ? w?.hourly_gold_g : w?.monthly_gold_g;
        if (!w || !v) return [];
        const t = typicalWage(row, scope.view);
        return [{
          id: iso,
          name: countryName(c),
          value: v,
          secondary: (hourly ? t?.hourly_gold_g : t?.monthly_gold_g) ?? null,
          highlight: scope.picks.includes(iso),
          tip: [
            ...wageNotes(w, scope.view, c, 160),
            ...(t ? wageNotes(t, scope.view, c, 120).map((x, i) => (i === 0 ? `中位数（同一调查）：${x}` : x)) : []),
            `当地金价：${money(row.gold_lcu_g, c.currency)}/克（${year} 年均）`,
            ...fxNote(row, c),
          ],
          table: [
            ...wageNotes(w, scope.view, c),
            ...(t ? wageNotes(t, scope.view, c).map((x, i) => (i === 0 ? `中位数（同一调查）：${x}` : x)) : []),
            ...fxNote(row, c),
            ...otherWages(row, w, scope.view, c),
          ],
        }];
      }),
    [rows, scope.picks, scope.view],
  );
  const cnW = primaryWage(scope.ds.countries.CHN?.years[scope.year], scope.view);
  // Largest gap between the official rate and the World Bank's GDP conversion factor, over the economies drawn.
  const fxGap = useMemo(() => {
    const ds = rows.filter(({ row }) => primaryWage(row, scope.view)).map(({ row }) => row.fx_vs_gdp_factor).filter((d): d is number => d != null);
    return ds.length ? Math.max(...ds.map((d) => Math.max(d, 1 / d))) - 1 : null;
  }, [rows, scope.view]);
  const option = useMemo(
    () => rankingOption({
      items,
      valueName: scope.view === "hourly" ? "平均时薪可换黄金" : "平均月薪可换黄金",
      secondaryName: scope.view === "hourly" ? "中位时薪可换黄金" : "中位月薪可换黄金",
      format: (v) => `${sig(v, 2)} 克`,
    }),
    [items, theme, scope.view],
  );

  return (
    <section className="block" id="gold">
      <h2>① 劳动 → 黄金：{scope.view === "hourly" ? "每小时" : "每月"}工资能换多少克黄金（{scope.year} 年）</h2>
      <p className="sub">
        工资 ÷（{scope.year} 年国际金价年均 ÷ 31.1034768 克/盎司 × 该年平均汇率）。这一步等价于把工资按市场汇率换成美元，再除以每克的美元金价。
      </p>
      <div className="card">
        <div className="legend">
          <span><span className="sw" style={{ background: "var(--accent)" }} />重点对比的经济体（平均{scope.view === "hourly" ? "时薪" : "月薪"}）</span>
          <span><span className="sw" style={{ background: "var(--deemph)" }} />其他经济体</span>
          <span><span className="sw" style={{ background: "var(--s2)", borderRadius: "50%" }} />同一调查的中位{scope.view === "hourly" ? "时薪" : "月薪"}（有数据时）</span>
        </div>
        <Chart option={option} height={rankingHeight(items.length)} ariaLabel={`各经济体${scope.view === "hourly" ? "每小时" : "每月"}工资可换黄金克数排名`} />
        <p className="note">
          工资的选用顺序：OECD 全职当量平均工资（时薪按 OECD 公布的全职雇员通常周工时折算）→ 国际劳工组织 ILOSTAT 覆盖全国全体雇员的平均工资
          （只有月薪的，用同一调查的每周实际工时折算）→ 国家统计机构自己的数据（中国国家统计局、美国劳工统计局，覆盖范围按其原文说明）→
          ILOSTAT 注明覆盖范围有限的记录（如只含城镇、只含私营部门、只含全职）。某经济体的主要口径与上一年不同时，悬停提示里会注明。
          {scope.ds.oecd_vs_survey && <>不同口径之间差距可能很大：同一经济体同一年 ILOSTAT 调查的平均月薪是 OECD 全职当量平均工资的
            {" "}{fmt(scope.ds.oecd_vs_survey.min, 2)}–{fmt(scope.ds.oecd_vs_survey.max, 2)} 倍（本项目数据中的 {scope.ds.oecd_vs_survey.n} 组对比），
            所以用不同口径的经济体之间的排序要谨慎看待；数据表里列出了同年的其他口径。</>}
          橙点是与条形同一调查的中位数，只在该调查同时发布了中位数时画出。
          {cnW && <>中国 {scope.year} 年用的是：{wageLabel(cnW, scope.view)}（{cnW.source}）。</>}
          每个经济体所用口径与发布方的注释见悬停提示和数据表。
          金价：世界银行 Pink Sheet 月均价的年平均；汇率：世界银行 WDI 年均官方汇率。它与世界银行换算该年 GDP 所用的因子逐年核对，相差在 ×/÷1.4 以内，
          只能证明两者是同一货币单位，不证明是同一个汇率（财年换算或多重汇率下两者会不同{fxGap != null && <>；本图 {scope.year} 年各经济体两者最多相差 {sig(fxGap * 100, 2)}%</>}），相差 0.5% 以上时悬停提示里会列出。
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
            <tr><th>经济体</th><th>平均工资 → 克金</th><th>中位工资 → 克金</th><th className="l">说明</th></tr>
          </thead>
          <tbody>
            {sorted.map((i) => (
              <tr key={i.id}>
                <td>{i.name}</td>
                <td>{sig(i.value)}</td>
                <td>{sig(i.secondary ?? null)}</td>
                <td className="l small ink2">{(i.table ?? i.tip).join("；")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
