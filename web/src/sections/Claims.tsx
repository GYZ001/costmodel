import type { Dataset } from "../types";
import { fmt, sig } from "../lib";

type Verdict = "ok" | "bad" | "mid";

interface Claim {
  said: string;
  verdict: Verdict;
  label: string;
  why: React.ReactNode;
}

export function Claims({ ds }: { ds: Dataset }) {
  const L = ds.latest;
  const g25 = ds.gold.annual["2025"];
  const cn25 = ds.countries.CHN?.years["2025"];
  const icp = ds.icp2021_pli_us.CHN;
  const cnFx25 = cn25?.fx;
  const nonpriv = cn25?.wages.find((w) => w.key === "cn_wage_nonprivate");
  const priv = cn25?.wages.find((w) => w.key === "cn_wage_private");
  const cnyAtSpot = L ? (4148 / ds.constants.grams_per_troy_ounce) * L.cny_per_usd : null;

  const claims: Claim[] = [
    {
      said: "美国 2026 年 8 月私营非农平均时薪 37.75 美元",
      verdict: "ok",
      label: "属实",
      why: <>BLS CES0500000003（季调）2026-08 为 {L ? fmt(L.period === "2026-08" ? L.us_ahe : NaN, 2) : "—"} 美元（初值，之后可能修订）。本页自动更新到 BLS 最新一期。</>,
    },
    {
      said: "中国 2025 年城镇非私营单位平均工资 129,441 元、私营单位 71,590 元",
      verdict: "ok",
      label: "属实",
      why: <>与国家统计局 2026-05-15 发布一致（本页抓取原文：{fmt(nonpriv ? nonpriv.monthly_lcu! * 12 : NaN, 0)} 元、{fmt(priv ? priv.monthly_lcu! * 12 : NaN, 0)} 元）。</>,
    },
    {
      said: "中国 2026 年 8 月食品价格同比 −1.4%，粮食 −0.6%，猪肉 −11.8%",
      verdict: "ok",
      label: "属实",
      why: <>与国家统计局 2026-09-09 CPI 发布及 9-15 国民经济运行发布一致。但同比涨跌只说明变化方向，不能说明两国价格水平谁高谁低。</>,
    },
    {
      said: "2026-09-29 COMEX 黄金约 4,148 美元/盎司，约 133.3 美元/克",
      verdict: "mid",
      label: "量级可信，本项目未核验日价",
      why: <>换算正确（4,148 ÷ 31.1035 = 133.36）。本项目只使用世界银行/IMF 的月均价；同期官方月均价：{ds.gold.monthly.slice(-1).map(([p, v]) => `${p} 为 ${fmt(v, 0)} 美元/盎司`)}。月工资应与同月均价配对，而不是某一天的期货价。</>,
    },
    {
      said: "1 克黄金在中国约 950 元",
      verdict: "bad",
      label: "与同期汇率不符",
      why: <>按文中 133.36 美元/克 和 {L ? `${L.period} 人民币月均汇率 ${fmt(L.cny_per_usd, 4)}` : "最新汇率"}，应约 {fmt(cnyAtSpot, 0)} 元/克；950 元对应约 7.12 的汇率，那是 2025 年的水平（2025 年均 {fmt(cnFx25, 4)}），2026 年人民币已明显升值。</>,
    },
    {
      said: "一年按 8 小时 × 250 天 = 2,000 小时折算，非私营 64.7 元/小时、私营 35.8 元/小时",
      verdict: "mid",
      label: "算术对，工时偏少",
      why: <>2,000 小时是法定标准工时。国家统计局调查的企业就业人员实际周工时约 48 小时（一年约 2,500 小时），按实际工时折算约 {fmt(nonpriv?.hourly_lcu, 1)} 元和 {fmt(priv?.hourly_lcu, 1)} 元/小时，低约 20%。</>,
    },
    {
      said: "用黄金计价，相当于把“汇率”剥掉了",
      verdict: "bad",
      label: "不成立",
      why: <>各地金价 ≈ 美元金价 × 汇率（上海金与国际金价的价差通常在 ±1% 量级），所以同一时点两国“克金时薪”之比 = 按市场汇率换算的美元时薪之比，汇率一点没少。黄金能去掉的是一国货币随时间的贬值，但同时引入了金价自身的大幅波动（见“黄金这把尺子”）。</>,
    },
    {
      said: "中国粮食、蔬菜、鸡蛋、猪肉等可贸易商品价格通常明显低于美国",
      verdict: "bad",
      label: "按官方比价不成立",
      why: icp ? (
        <>世界银行 ICP 2021 按统一规格比价：中国“食品与非酒精饮料”价格水平是美国的 {fmt(icp.food_nonalc, 2)} 倍（肉类 {fmt(icp.meat, 2)}、奶蛋 {fmt(icp.milk_cheese_eggs, 2)}、蔬菜 {fmt(icp.vegetables, 2)}、面包谷物 {fmt(icp.bread_cereals, 2)}）。
          只在“最低成本健康饮食”口径下（只挑最便宜的食物）中国更便宜：2025 年 {fmt(cn25?.cohd.total, 1)} 元/天，按当年汇率约 {fmt(cn25?.cohd.total && cnFx25 ? cn25.cohd.total / cnFx25 : NaN, 2)} 美元，美国 {fmt(ds.countries.USA?.years["2025"]?.cohd.total, 2)} 美元。</>
      ) : <>见“什么贵、什么便宜”。</>,
    },
    {
      said: "美国房租、医疗、餐饮等服务很贵，而超市是商品消费，所以“黄金购买力”会把两国差距压缩不少",
      verdict: "bad",
      label: "推理方向反了",
      why: icp ? (
        <>正因为两国价差主要在服务（ICP 2021：中国住房 {fmt(icp.housing, 2)}、医疗 {fmt(icp.health, 2)}、餐饮住宿 {fmt(icp.restaurants_hotels, 2)} 倍于美国），只看超市商品时差距被压缩得<strong>更少</strong>；
          把全部居民消费算进来（{cn25?.pli_hfce ? `2025 年整体价格水平为美国的 ${fmt(cn25.pli_hfce, 2)} 倍` : "购买力平价"}），压缩才最多。</>
      ) : <>见“什么贵、什么便宜”。</>,
    },
    {
      said: "劳动购买力 =（时薪 ÷ 黄金价格）×（1 克黄金能买多少商品）",
      verdict: "ok",
      label: "公式对，但黄金被约掉",
      why: <>两项相乘 = 时薪 ÷ 商品价格，结果与是否经过黄金无关。黄金克数只是中间读数，适合直观感受第一步的差距。本页的“三步换算”就是按这个公式做的。</>,
    },
  ];

  const usg = L ? L.us_gold_g_per_hour : null;
  return (
    <section className="block" id="claims">
      <h2>核对之前对话中的说法</h2>
      <p className="sub">
        下面逐条核对之前那轮讨论里的事实和推理。数字取自本页数据管道抓取的官方原文，随数据刷新自动更新；无法用官方数据核验的，会明确写出来。
      </p>
      <div className="card">
        <div className="table-scroll" style={{ maxHeight: "none" }}>
          <table className="data">
            <thead><tr><th className="l">之前的说法</th><th className="l">结论</th><th className="l">依据</th></tr></thead>
            <tbody>
              {claims.map((c) => (
                <tr key={c.said}>
                  <td className="l" style={{ minWidth: 220 }}>{c.said}</td>
                  <td className="l"><span className={`verdict ${c.verdict}`}>{c.label}</span></td>
                  <td className="l small" style={{ minWidth: 320 }}>{c.why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {L && g25 && (
          <p className="note">
            用同期数据重算：美国 {L.period} 时薪 {fmt(L.us_ahe, 2)} 美元 ÷ 同月均价 {fmt(L.gold_usd_g, 2)} 美元/克 = {sig(usg, 3)} 克/小时；
            中国 2025 年工资应配 2025 年均金价 {fmt(g25.usd_oz, 0)} 美元/盎司和 2025 年均汇率，结果见“三步换算”和“中美细看”。
          </p>
        )}
      </div>
    </section>
  );
}
