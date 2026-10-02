import type { Dataset } from "../types";
import { fmt, primaryWage, sig, wageYears } from "../lib";

type Verdict = "ok" | "bad" | "mid";

interface Claim {
  said: string;
  verdict: Verdict;
  label: string;
  why: React.ReactNode;
}

const MARK: Record<Verdict, string> = { ok: "✓", bad: "✗", mid: "≈" };

// Numbers as written in the earlier conversation.
const SAID = {
  spotUsdOz: 4148,
  usAhe: 37.75,
  usAheMonth: "2026-08",
  cnyPerGram: 950,
  /** The spot price above is of 2026-09-29: the 950 yuan is checked with that month's CNY rate. */
  fxMonth: "2026-09",
  cnNonprivate: 129441,
  cnPrivate: 71590,
  cnWageYear: "2025",
  cpiMonth: "2026-08",
  cpi: [
    { item: "食品", dir: "下降", value: 1.4 },
    { item: "粮食", dir: "下降", value: 0.6 },
    { item: "猪肉", dir: "下降", value: 11.8 },
  ],
};

type Release = Dataset["cn_cpi_yoy"][number];

/** "X价格(同比)?上涨/下降N%" or "X价格(同比)?持平" where X starts a clause, so "非食品价格" is
 *  not read as "食品价格".  Only clauses the pipeline found to report this month's
 *  year-on-year change are searched; releases are searched in the order given (the CPI
 *  release before the economy release). */
function findChange(releases: Release[], item: string): { dir: string; value: number; sentence: string; release: Release } | null {
  const rx = new RegExp(`(?:^|其中)${item}价格(?:同比)?(?:(上涨|下降)([\\d.]+)%|(持平))`);
  for (const release of releases) {
    for (const s of release.sentences) {
      for (const clause of s.yoy) {
        const m = clause.match(rx);
        if (m) return { dir: m[3] ?? m[1], value: m[3] ? 0 : Number(m[2]), sentence: s.text, release };
      }
    }
  }
  return null;
}

export function Claims({ ds }: { ds: Dataset }) {
  const G = ds.constants.grams_per_troy_ounce;
  const L = ds.latest;
  const spotG = SAID.spotUsdOz / G;
  const gm = ds.gold.monthly;
  const goldLast = gm[gm.length - 1];
  const ahe = ds.us_monthly.us_ahe_all_sa.find(([p]) => p === SAID.usAheMonth);
  const cny = ds.fx_recent_ecb.CHN ?? [];
  const cnyAt = (month: string) => cny.find(([p]) => p === month)?.[1];
  const cnySpot = cnyAt(SAID.fxMonth);
  const cn = (L?.cn ?? []).filter((r) => r.wage_year === SAID.cnWageYear);
  const cnOf = (series: string, basis: "assumed" | "actual") => cn.find((r) => r.series === series && r.basis === basis);
  const np = { st: cnOf("cn_wage_nonprivate", "assumed"), ac: cnOf("cn_wage_nonprivate", "actual") };
  const pv = { st: cnOf("cn_wage_private", "assumed"), ac: cnOf("cn_wage_private", "actual") };
  const icp = ds.icp2021_pli_us.CHN;

  // Latest year in which both the US and China have an hourly wage and every price measure.
  const cmpYear = (ds.countries.CHN ? wageYears(ds.countries.CHN, "hourly") : []).find((y) => {
    const a = primaryWage(ds.countries.USA?.years[y], "hourly");
    const b = primaryWage(ds.countries.CHN?.years[y], "hourly");
    return a?.hourly_gold_g && a.hourly_ppp && a.minutes_per_cohd_day && b?.hourly_gold_g && b.hourly_ppp && b.minutes_per_cohd_day;
  });
  const usW = cmpYear ? primaryWage(ds.countries.USA.years[cmpYear], "hourly") : undefined;
  const cnW = cmpYear ? primaryWage(ds.countries.CHN.years[cmpYear], "hourly") : undefined;
  const ratio = usW && cnW ? {
    gold: usW.hourly_gold_g! / cnW.hourly_gold_g!,
    diet: cnW.minutes_per_cohd_day! / usW.minutes_per_cohd_day!,
    ppp: usW.hourly_ppp! / cnW.hourly_ppp!,
  } : null;

  // Cost of the cheapest healthy diet, China ÷ US at each year's market rate.
  const cohdRatio = (y: string) => {
    const c = ds.countries.CHN?.years[y];
    const u = ds.countries.USA?.years[y];
    return c?.cohd.total && c.fx && u?.cohd.total ? c.cohd.total / c.fx / u.cohd.total : null;
  };
  const cohdYears = Object.keys(ds.countries.CHN?.years ?? {}).filter((y) => cohdRatio(y) != null).sort();
  const cohdLastYear = cohdYears[cohdYears.length - 1];

  const claims: Claim[] = [];

  claims.push({
    said: `2026 年 9 月 29 日 COMEX 黄金约 ${fmt(SAID.spotUsdOz, 0)} 美元/盎司，折合约 133.3 美元/克`,
    verdict: "mid",
    label: "本项目未核验当日价格",
    why: <>换算：{fmt(SAID.spotUsdOz, 0)} ÷ {fmt(G, 4)} = {fmt(spotG, 2)} 美元/克。本项目只用世界银行 Pink Sheet 的月均价（工作簿{ds.gold.source_updated ? `注明更新于 ${ds.gold.source_updated}` : ""}），
      目前最新为 {goldLast[0]}：{fmt(goldLast[1], 0)} 美元/盎司。期货某一天的价格不宜与一个月的平均工资配对。</>,
  });

  if (!ahe) {
    claims.push({ said: `美国 2026 年 8 月私营非农平均时薪 ${SAID.usAhe} 美元`, verdict: "mid", label: "本项目数据中没有该月", why: <>BLS CES0500000003 在本次抓取中没有 {SAID.usAheMonth} 的数值。</> });
  } else {
    const same = Math.abs(ahe[1] - SAID.usAhe) < 0.005;
    claims.push({
      said: `美国 2026 年 8 月私营非农平均时薪 ${SAID.usAhe} 美元`,
      verdict: same ? "ok" : "bad",
      label: same ? "属实" : "与 BLS 当前数值不同",
      why: <>BLS CES0500000003（全部私营雇员，季调）{SAID.usAheMonth} 当前为 {fmt(ahe[1], 2)} 美元
        {ahe[3] ? "，BLS 标注为初值，之后可能修订" : "，BLS 已不再标注为初值"}。</>,
    });
    claims.push({
      said: `美国 1 小时工资 ≈ 0.283 克黄金`,
      verdict: "mid",
      label: "算术对，金价与工资不同期",
      why: <>{SAID.usAhe} ÷ {fmt(spotG, 2)} = {sig(SAID.usAhe / spotG, 3)}。但这是 {SAID.usAheMonth} 的月平均工资配 9 月底某一天的期货价。
        配同月（{SAID.usAheMonth}）月均金价 {fmt(gm.find(([p]) => p === SAID.usAheMonth)?.[1], 0)} 美元/盎司，是 <strong>{sig(ahe[2], 3)} 克/小时</strong>。</>,
    });
  }

  if (!(np.st && pv.st)) {
    claims.push({
      said: `中国 ${SAID.cnWageYear} 年城镇非私营单位平均工资 ${fmt(SAID.cnNonprivate, 0)} 元/年，私营单位 ${fmt(SAID.cnPrivate, 0)} 元/年；按 2,000 小时折算的时薪；1 克黄金约 ${SAID.cnyPerGram} 元`,
      verdict: "mid",
      label: "本项目数据中没有该年工资",
      why: <>本项目存档的国家统计局发布中没有 {SAID.cnWageYear} 年城镇非私营、私营单位平均工资，这几条无法核对。</>,
    });
  }

  if (np.st && pv.st) {
    const same = np.st.annual === SAID.cnNonprivate && pv.st.annual === SAID.cnPrivate;
    claims.push({
      said: `中国 ${SAID.cnWageYear} 年城镇非私营单位平均工资 ${fmt(SAID.cnNonprivate, 0)} 元/年，私营单位 ${fmt(SAID.cnPrivate, 0)} 元/年`,
      verdict: same ? "ok" : "bad",
      label: same ? "属实" : "与国家统计局发布不同",
      why: <>国家统计局《{SAID.cnWageYear}年城镇单位就业人员年平均工资情况》原文（本项目已存档）：非私营 {fmt(np.st.annual, 0)} 元，私营 {fmt(pv.st.annual, 0)} 元。</>,
    });
  }

  if (np.st && pv.st) {
    const weekly = np.ac ? np.ac.hours_year / 52 : null;
    claims.push({
      said: "按 8 小时 × 250 天 = 2,000 小时折算：非私营约 64.7 元/小时，私营约 35.8 元/小时",
      verdict: "mid",
      label: np.ac && np.ac.hours_year > 2000 ? "算术对，工时偏少" : "算术对",
      why: <>{fmt(np.st.annual, 0)} ÷ 2,000 = {fmt(np.st.hourly, 1)}，{fmt(pv.st.annual, 0)} ÷ 2,000 = {fmt(pv.st.hourly, 1)}。2,000 小时是原文采用的折算假设，本项目没有存档关于法定年工作日的文件，不判断它是否为法定标准。
        {np.ac && pv.ac && weekly && <> 国家统计局月度劳动力调查的“企业就业人员周平均工作时间”，{SAID.cnWageYear} 年本项目存档的 {np.ac.hours_months?.length ?? 0} 个月平均为 {fmt(weekly, 1)} 小时，
          折合一年约 {fmt(np.ac.hours_year, 0)} 小时；按调查工时算，非私营约 {fmt(np.ac.hourly, 1)} 元/小时、私营约 {fmt(pv.ac.hourly, 1)} 元/小时，
          比按 2,000 小时算{np.ac.hours_year > 2000 ? "低" : "高"} {fmt(Math.abs(1 - 2000 / np.ac.hours_year) * 100, 0)}%。
          （该工时是全部企业就业人员的平均，并非分别对应非私营、私营单位。）</>}</>,
    });
  }

  if (L && np.st && pv.st) {
    const atSpot = cnySpot != null ? spotG * cnySpot : null;
    // "约 950" is stated to the nearest 10 yuan, so it is consistent within ±5 yuan.
    const consistent = atSpot != null && Math.abs(SAID.cnyPerGram - atSpot) <= 5;
    // The same month's average gold price (Pink Sheet) and CNY rate, for comparison.
    const goldMonth = gm.find(([p]) => p === SAID.usAheMonth)?.[1];
    const cnyMonth = cnyAt(SAID.usAheMonth);
    const monthly = goldMonth != null && cnyMonth != null ? (goldMonth / G) * cnyMonth : null;
    const nearerMonthly = atSpot != null && monthly != null && Math.abs(SAID.cnyPerGram - monthly) < Math.abs(SAID.cnyPerGram - atSpot);
    const ratioSt = np.st.gold_g_per_hour / L.us_gold_g_per_hour;
    claims.push({
      said: `1 克黄金在中国约 ${SAID.cnyPerGram} 元，所以中国非私营约 0.068 克/小时、私营约 0.038 克/小时，以美国为 1 分别为 0.24 和 0.13`,
      verdict: consistent ? "ok" : "mid",
      label: atSpot == null ? "本项目没有该月汇率" : consistent ? "与文中金价相符" : "与文中美元金价不自洽",
      why: <>{atSpot == null ? <>本项目存档的欧洲央行参考汇率中没有 {SAID.fxMonth} 的人民币汇率，无法按文中金价核对。</> : <>
        按文中 {fmt(spotG, 2)} 美元/克和 {SAID.fxMonth} 人民币月均汇率 {fmt(cnySpot, 3)}（欧洲央行参考汇率交叉折算），应约 <strong>{fmt(atSpot, 0)} 元/克</strong>
        {consistent ? "，与约 950 元相符。" : <>，与约 950 元相差 {fmt(Math.abs(SAID.cnyPerGram / atSpot - 1) * 100, 0)}%
          {nearerMonthly && monthly != null ? `；950 元更接近 ${SAID.usAheMonth} 月均金价 × 同月汇率折算的 ${fmt(monthly, 0)} 元/克` : ""}。美国用一个金价、中国用另一个金价，两国的比值就带进了这一偏差。</>}</>}
        两边统一用 {L.period} 的金价和汇率：美国 {sig(L.us_gold_g_per_hour, 3)} 克/小时，中国非私营（2,000 小时）{sig(np.st.gold_g_per_hour, 2)} 克/小时，比值 {fmt(ratioSt, 2)}；
        按调查工时为 {np.ac ? fmt(np.ac.gold_g_per_hour / L.us_gold_g_per_hour, 2) : "—"}。两边用同一金价时金价被约掉，这个比值只取决于两国工资和汇率；另外中国用的是 {SAID.cnWageYear} 年全年工资，美国是 {L.period} 当月工资。</>,
    });
  }

  claims.push({
    said: "用黄金作计价单位，相当于把“汇率”和部分货币贬值因素剥掉了",
    verdict: "bad",
    label: "汇率没有被剥掉",
    why: <>本项目计算各地金价用的是“美元金价 × 汇率”，于是同一时点两国“每小时能换几克金”之比，恒等于按市场汇率换算的美元时薪之比——汇率原封不动地留在结果里。
      各国本地市场的实际金价还可能因进口管制、税费等偏离这个换算，本项目没有采用各国本地金价。黄金能去掉的是一国货币随时间的贬值，但同时带进了金价自身的大幅波动（见“黄金这把尺子”）。</>,
  });

  if (icp) {
    const items = [
      { name: "粮食", key: "bread_cereals", icpName: "面包谷物" },
      { name: "蔬菜", key: "vegetables", icpName: "蔬菜" },
      { name: "鸡蛋", key: "milk_cheese_eggs", icpName: "奶、奶酪和蛋（合并统计）" },
      { name: "猪肉", key: "meat", icpName: "全部肉类（无单独猪肉）" },
    ].filter((x) => icp[x.key] != null);
    const lower = items.filter((x) => icp[x.key] < 1);
    const foodLower = icp.food_nonalc != null && icp.food_nonalc < 1;
    const verdict: Verdict = lower.length === items.length && foodLower ? "ok" : lower.length === 0 && !foodLower ? "bad" : "mid";
    const r21 = cohdRatio("2021");
    const rLast = cohdLastYear ? cohdRatio(cohdLastYear) : null;
    const cy = (y: string) => ds.countries.CHN?.years[y];
    const uy = (y: string) => ds.countries.USA?.years[y];
    const chg = (a?: number | null, b?: number | null) => (a && b ? (b / a - 1) * 100 : null);
    const cnChg = cohdLastYear ? chg(cy("2021")?.cohd.total, cy(cohdLastYear)?.cohd.total) : null;
    const usChg = cohdLastYear ? chg(uy("2021")?.cohd.total, uy(cohdLastYear)?.cohd.total) : null;
    const signed = (x: number | null) => (x == null ? "—" : `${x >= 0 ? "+" : ""}${fmt(x, 1)}%`);
    claims.push({
      said: "中国粮食、蔬菜、鸡蛋、猪肉等价格通常明显低于美国",
      verdict,
      label: `2021 年：${items.length} 项中 ${lower.length} 项低于美国，食品整体${foodLower ? "低于" : "高于"}美国`,
      why: <>世界银行 ICP 2021 按统一规格比价、按市场汇率换算（美国 = 1）：{items.map((x) => `${x.icpName} ${fmt(icp[x.key], 2)}`).join("，")}；
        食品与非酒精饮料整体 {fmt(icp.food_nonalc, 2)}。{lower.length > 0 && lower.length < items.length && <>低于美国的只有{lower.map((x) => x.name).join("、")}。</>}
        “明显”没有可核对的标准，这里只看是否低于美国。
        {r21 != null && rLast != null && cohdLastYear !== "2021" && <> 2021 年之后的变化：世界银行公布的一人一天最低成本健康饮食（本币），2021 年到 {cohdLastYear} 年中国 {signed(cnChg)}、美国 {signed(usChg)}；
          人民币年均汇率从 {fmt(cy("2021")?.fx, 3)} 变为 {fmt(cy(cohdLastYear)?.fx, 3)} 元/美元。两者合起来，按当年汇率折算的中国 ÷ 美国从 {fmt(r21, 2)} 变为 {fmt(rLast, 2)}。
          存档数据里只有 2021 年有六类食物的分项，其他年份只有总额；本项目只存档了 ICP 2021 的结果，所以今天各类食品的确切价差本项目给不出。</>}</>,
    });
  }

  if (ratio && cmpYear && icp) {
    const compresses = ratio.diet < ratio.gold;
    const servicesFurther = ratio.ppp < ratio.diet;
    const food = icp.food_nonalc;
    claims.push({
      said: "美国房租、医疗、餐饮等服务很贵，而超市属于商品消费，所以“黄金购买力”会把两国差距压缩不少",
      verdict: "mid",
      label: compresses ? "压缩多少取决于买什么；理由不对" : "按健康饮食成本没有压缩",
      why: <>{cmpYear} 年（美国：{usW!.label}；中国：{cnW!.label}）美国时薪是中国的：按黄金克数 <strong>{fmt(ratio.gold, 1)} 倍</strong>，
        按“一人一天最低成本健康饮食”算 <strong>{fmt(ratio.diet, 1)} 倍</strong>，按全部居民消费的购买力平价算 <strong>{fmt(ratio.ppp, 1)} 倍</strong>。
        只看食物时，结果取决于买什么：只挑最便宜的健康食物，差距{compresses ? `从 ${fmt(ratio.gold, 1)} 倍缩到 ${fmt(ratio.diet, 1)} 倍` : "没有缩小"}；
        按 ICP 2021 全部食品的平均价格，2021 年中国是美国的 {fmt(food, 2)} 倍；{cmpYear} 年的食品整体价差本项目无法给出（只存档了 ICP 2021）。
        原文的理由是美国房租、医疗等服务贵（ICP 2021，美国 = 1：中国住房 {fmt(icp.housing, 2)}、医疗 {fmt(icp.health, 2)}、餐饮住宿 {fmt(icp.restaurants_hotels, 2)}），
        但超市恰恰不含服务，这个理由与“超市比价压缩差距”不相干
        {servicesFurther ? `；服务价差体现在把全部消费算进来之后，差距进一步缩到 ${fmt(ratio.ppp, 1)} 倍` : ""}。</>,
    });
  }

  const cpiReleases = ds.cn_cpi_yoy
    .filter((r) => r.period === SAID.cpiMonth)
    .sort((a, b) => (a.kind === b.kind ? 0 : a.kind === "cpi" ? -1 : 1));
  const cpiSaid = "中国 2026 年 8 月食品价格同比下降 1.4%，粮食下降 0.6%，猪肉下降 11.8%";
  if (!cpiReleases.length) {
    claims.push({
      said: cpiSaid,
      verdict: "mid",
      label: "本项目尚未存档该月发布",
      why: <>本项目存档的国家统计局居民消费价格与国民经济运行月度发布中没有 {SAID.cpiMonth} 的同比原句，无法核对。</>,
    });
  } else {
    const found = SAID.cpi.map((c) => ({ ...c, hit: findChange(cpiReleases, c.item) }));
    const same = (f: (typeof found)[number]) => f.hit && f.hit.dir === f.dir && Math.abs(f.hit.value - f.value) < 1e-9;
    const allSame = found.every(same);
    const anyDiff = found.some((f) => f.hit && !same(f));
    const bySource = new Map<string, { release: Release; sentences: Set<string> }>();
    for (const f of found) {
      if (!f.hit) continue;
      const g = bySource.get(f.hit.release.url) ?? { release: f.hit.release, sentences: new Set<string>() };
      g.sentences.add(f.hit.sentence);
      bySource.set(f.hit.release.url, g);
    }
    const notFound = found.filter((f) => !f.hit).map((f) => f.item);
    claims.push({
      said: cpiSaid,
      verdict: allSame ? "ok" : anyDiff ? "bad" : "mid",
      label: allSame ? "属实" : anyDiff ? "与原文不符" : "原文中未全部找到",
      why: <>
        {[...bySource.values()].map(({ release, sentences }) => (
          <span key={release.url}>国家统计局《<a href={release.url}>{release.title}</a>》原文（已存档）：{[...sentences].map((q) => `“${q}”`).join(" ")} </span>
        ))}
        {notFound.length > 0 && <>同比原句中未找到：{notFound.join("、")}。</>}
        但同比涨跌只说明价格的变化方向，不能说明两国价格水平谁高谁低。</>,
    });
  }

  claims.push({
    said: "劳动购买力 =（时薪 ÷ 黄金价格）×（1 克黄金能买多少商品）",
    verdict: "ok",
    label: "公式对，但黄金被约掉",
    why: <>两项相乘 = 时薪 ÷ 商品价格，结果与是否经过黄金无关。黄金克数只是中间读数，适合直观感受第一步的差距。本页的“三步换算”就是按这个公式做的。</>,
  });

  if (ratio && cmpYear) {
    const partly = ratio.ppp > 1 && ratio.ppp < ratio.gold;
    claims.push({
      said: "美国劳动者的“黄金收入优势”会被美国较高的物价部分抵消，但不会完全抵消",
      verdict: partly ? "ok" : "mid",
      label: partly ? "属实" : ratio.ppp <= 1 ? "被完全抵消" : "没有被抵消",
      why: <>{cmpYear} 年：按黄金克数美国时薪是中国的 {fmt(ratio.gold, 1)} 倍，扣除两国居民消费物价差异后（购买力平价）是 {fmt(ratio.ppp, 1)} 倍。
        {partly ? "差距缩小了，但没有消失。" : ""}</>,
    });
  }

  return (
    <section className="block" id="claims">
      <h2>核对之前对话中的说法</h2>
      <p className="sub">
        下面逐条核对之前那轮讨论里的事实和推理。结论和数字都由本页数据管道存档的官方原文计算，随数据刷新自动更新；无法用官方数据核验的，会明确写出来。
      </p>
      <div className="card">
        <div className="table-scroll" style={{ maxHeight: "none" }}>
          <table className="data">
            <thead><tr><th className="l">之前的说法</th><th className="l">结论</th><th className="l">依据</th></tr></thead>
            <tbody>
              {claims.map((c) => (
                <tr key={c.said}>
                  <td className="l" style={{ minWidth: 220 }}>{c.said}</td>
                  <td className="l"><span className={`verdict ${c.verdict}`}><span aria-hidden>{MARK[c.verdict]} </span>{c.label}</span></td>
                  <td className="l small" style={{ minWidth: 320 }}>{c.why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
