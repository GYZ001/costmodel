import { useMemo } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { linesOption } from "../charts";
import { countryName, fmt, sig, useThemeVersion } from "../lib";

export function GoldRuler({ ds, picks, slotOf }: Scope) {
  const theme = useThemeVersion();
  const us = ds.us_monthly;
  const pns = us.us_ahe_pns_sa;
  const all = us.us_ahe_all_sa;

  const usOpt = useMemo(
    () => linesOption({
      series: [
        { name: "生产与非管理岗位", points: pns.map(([p, , g]) => [p, g]), colorIndex: 0 },
        { name: "全部私营雇员", points: all.map(([p, , g]) => [p, g]), colorIndex: 1 },
      ],
      yName: "克黄金/小时",
      format: (v) => sig(v, 2),
      log: true,
    }),
    [pns, all, theme],
  );
  const goldOpt = useMemo(
    () => linesOption({
      series: [{ name: "金价", points: ds.gold.monthly.filter(([p]) => p >= "1964-01").map(([p, v]) => [p, v]), colorIndex: 3 }],
      yName: "美元/盎司",
      format: (v) => fmt(v, 0),
      log: true,
    }),
    [ds, theme],
  );

  const hist = useMemo(() => {
    return picks
      .filter((iso) => ds.wage_gold_history[iso])
      .map((iso) => ({
        iso,
        name: countryName(ds.countries[iso]),
        points: ds.wage_gold_history[iso].points.map(([y, , g]) => [`${y}`, g] as [string, number]),
        colorIndex: slotOf[iso],
      }));
  }, [ds, picks, slotOf]);
  const noHistory = picks.filter((iso) => !ds.wage_gold_history[iso]).map((iso) => countryName(ds.countries[iso]));
  const histOpt = useMemo(() => linesOption({ series: hist, yName: "月薪可换黄金（克）", format: (v) => sig(v, 2), log: true }), [hist, theme]);

  const first = pns[0];
  const peak = pns.reduce((a, b) => (b[2] > a[2] ? b : a), pns[0]);
  const last = pns[pns.length - 1];

  return (
    <section className="block" id="ruler">
      <h2>黄金是一把会伸缩的尺子</h2>
      <p className="sub">
        用黄金计价能剥掉货币本身的贬值，但金价自己波动极大：同一份工资折成黄金，几年之内可以翻倍或腰斩。
        下图是美国生产与非管理岗位的平均时薪折成黄金克数（每月工资配当月金价）。
      </p>
      <div className="callout">
        {first && peak && last && (
          <>
            美国这一口径的时薪：{first[0].slice(0, 4)} 年约合 <strong>{sig(first[2], 2)} 克</strong>黄金/小时，
            {peak[0].slice(0, 7)} 最高 <strong>{sig(peak[2], 2)} 克</strong>，{last[0]} 只有 <strong>{sig(last[2], 2)} 克</strong>；
            同期美元时薪从 {fmt(first[1], 2)} 美元涨到 {fmt(last[1], 2)} 美元。克数的起落主要反映金价，而不是生活水平。
          </>
        )}
      </div>
      <div className="grid2">
        <div className="card">
          <h3>美国时薪折合黄金（克/小时，对数刻度）</h3>
          <div className="legend">
            <span><span className="ln" style={{ background: "var(--s1)" }} />生产与非管理岗位（1964 年起）</span>
            <span><span className="ln" style={{ background: "var(--s2)" }} />全部私营雇员（2006 年起）</span>
          </div>
          <Chart option={usOpt} height={320} ariaLabel="美国时薪折合黄金克数" />
          <p className="note">工资：BLS CES0500000008 / CES0500000003（季调）；金价：世界银行 Pink Sheet 月均价。</p>
        </div>
        <div className="card">
          <h3>同期金价（美元/盎司，对数刻度）</h3>
          <Chart option={goldOpt} height={320} ariaLabel="国际金价月均" />
          <p className="note">世界银行 Pink Sheet 月均价。两张图分开画，避免双纵轴制造虚假的相关。</p>
        </div>
      </div>
      <div className="card">
        <h3>重点经济体：平均月薪折合黄金（克，年度，对数刻度）</h3>
        <div className="legend">
          {hist.map((s) => (
            <span key={s.iso}><span className="ln" style={{ background: `var(--s${s.colorIndex + 1})` }} />{s.name}</span>
          ))}
        </div>
        <Chart option={histOpt} height={360} ariaLabel="重点经济体月薪折合黄金克数" />
        <p className="note">
          每年的月薪用当年平均金价和平均汇率折算。口径：{hist.map((s) => `${s.name}＝${ds.wage_gold_history[s.iso].label}`).join("；")}。
          {noHistory.length > 0 && <>没有可核对的历年月薪序列：{noHistory.join("、")}。</>}
        </p>
      </div>
    </section>
  );
}
