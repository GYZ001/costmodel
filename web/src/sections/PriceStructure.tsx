import { useMemo } from "react";
import type { Scope } from "../App";
import { Chart } from "../Chart";
import { heatmapOption } from "../charts";
import { countryName, fmt, useThemeVersion } from "../lib";

// Food sub-groups shown in the China callout, split by whether they cost more or less than in the US.
const FOOD_SUBS: { key: string; name: string }[] = [
  { key: "bread_cereals", name: "面包谷物" },
  { key: "meat", name: "肉类" },
  { key: "fish", name: "水产" },
  { key: "milk_cheese_eggs", name: "奶蛋" },
  { key: "oils_fats", name: "油脂" },
  { key: "fruit", name: "水果" },
  { key: "vegetables", name: "蔬菜" },
];
const SERVICES = ["housing", "health", "education", "restaurants_hotels"];

function quartiles(v: number[]): [number, number, number] {
  const s = [...v].sort((a, b) => a - b);
  const q = (p: number) => {
    const i = (s.length - 1) * p;
    const lo = Math.floor(i);
    return s[lo] + (s[Math.min(lo + 1, s.length - 1)] - s[lo]) * (i - lo);
  };
  return [q(0.25), q(0.5), q(0.75)];
}

const CATS: { key: string; name: string }[] = [
  { key: "hfce", name: "居民消费" },
  { key: "food_nonalc", name: "食品饮料" },
  { key: "bread_cereals", name: "面包谷物" },
  { key: "meat", name: "肉类" },
  { key: "milk_cheese_eggs", name: "奶蛋" },
  { key: "fruit", name: "水果" },
  { key: "vegetables", name: "蔬菜" },
  { key: "clothing", name: "衣着" },
  { key: "housing", name: "住房水电" },
  { key: "health", name: "医疗" },
  { key: "transport", name: "交通" },
  { key: "communication", name: "通信" },
  { key: "education", name: "教育" },
  { key: "restaurants_hotels", name: "餐饮住宿" },
];

export function PriceStructure(scope: Scope) {
  const theme = useThemeVersion();
  const { ds, group, picks } = scope;
  const { rows, values, isos } = useMemo(() => {
    const isos = Object.keys(ds.icp2021_pli_us)
      .filter((iso) => ds.countries[iso] && (group === "all" ? true : ds.countries[iso].g20 || picks.includes(iso)))
      .sort((a, b) => (ds.icp2021_pli_us[b].hfce ?? 0) - (ds.icp2021_pli_us[a].hfce ?? 0));
    const rows = isos.map((iso) => countryName(ds.countries[iso]));
    const values: [number, number, number | null][] = [];
    isos.forEach((iso, r) => CATS.forEach((cat, c) => values.push([c, r, ds.icp2021_pli_us[iso][cat.key] ?? null])));
    return { rows, values, isos };
  }, [ds, group, picks]);
  const hl = useMemo(() => new Set(picks.filter((p) => ds.countries[p]).map((p) => countryName(ds.countries[p]))), [ds, picks]);
  const option = useMemo(() => heatmapOption({ rows, cols: CATS.map((c) => c.name), values, highlightRows: hl }), [rows, values, hl, theme]);
  const cn = ds.icp2021_pli_us.CHN;
  const spread = useMemo(() => {
    const all = Object.values(ds.icp2021_pli_us);
    const of = (key: string) => {
      const v = all.map((r) => r[key]).filter((x): x is number => x != null);
      return { key, name: CATS.find((c) => c.key === key)!.name, n: v.length, q: quartiles(v) };
    };
    return { food: of("food_nonalc"), services: SERVICES.map(of) };
  }, [ds]);
  // Cheapest healthy diet, China ÷ US at each year's market rate: the only official food-price comparison after 2021.
  const cohdTrend = useMemo(() => {
    const c = ds.countries.CHN?.years ?? {};
    const u = ds.countries.USA?.years ?? {};
    const r = (y: string) => (c[y]?.cohd.total && c[y].fx && u[y]?.cohd.total ? c[y].cohd.total! / c[y].fx / u[y].cohd.total! : null);
    const ys = Object.keys(c).filter((y) => r(y) != null).sort();
    const last = ys[ys.length - 1];
    return last && last !== "2021" && r("2021") != null ? { last, r21: r("2021")!, rLast: r(last)! } : null;
  }, [ds]);
  const cheaper = cn ? FOOD_SUBS.filter((f) => cn[f.key] != null && cn[f.key]! < 1) : [];
  const dearer = cn ? FOOD_SUBS.filter((f) => cn[f.key] != null && cn[f.key]! >= 1) : [];
  const listOf = (fs: typeof FOOD_SUBS) => fs.map((f) => `${f.name} ${fmt(cn![f.key], 2)}`).join("、");

  return (
    <section className="block" id="structure">
      <h2>什么贵、什么便宜：各类商品和服务的价格水平</h2>
      <p className="sub">
        世界银行国际比较项目（ICP）2021 年基准：用统一规格的商品和服务逐项比价，按市场汇率换算后与美国比较（美国 = 1）。
        红色表示比美国贵，蓝色表示比美国便宜。
        在 {spread.food.n} 个经济体中，食品与非酒精饮料价格水平的中位数为美国的 {fmt(spread.food.q[1], 2)} 倍（中间一半的经济体在 {fmt(spread.food.q[0], 2)}–{fmt(spread.food.q[2], 2)} 之间）；
        而{spread.services.map((s) => `${s.name}中位数 ${fmt(s.q[1], 2)}（${fmt(s.q[0], 2)}–${fmt(s.q[2], 2)}）`).join("、")}。
        食品这类可以跨境贸易的商品，各国价格离美国更近；不能贸易的本地服务，价差大得多。
      </p>
      {cn && cn.hfce != null && cn.food_nonalc != null && (
        <div className="callout">
          以中国为例（2021 年，美国 = 1）：居民消费整体价格水平为 <strong>{fmt(cn.hfce, 2)}</strong>，
          “食品与非酒精饮料”为 <strong>{fmt(cn.food_nonalc, 2)}</strong>；
          {dearer.length > 0 && <>其中不低于美国的有{listOf(dearer)}</>}
          {dearer.length > 0 && cheaper.length > 0 && "，"}
          {cheaper.length > 0 && <>低于美国的有{listOf(cheaper)}</>}。
          住房 {fmt(cn.housing, 2)}、医疗 {fmt(cn.health, 2)}、餐饮住宿 {fmt(cn.restaurants_hotels, 2)}。
          {cn.food_nonalc >= 1
            ? "按市场汇率，中国的食品整体并不比美国便宜，整体物价低主要来自服务。"
            : `按市场汇率，中国的食品整体比美国便宜约 ${fmt((1 - cn.food_nonalc) * 100, 0)}%，但服务便宜得更多。`}
          {cohdTrend && <> 这是 2021 年的情况。之后人民币汇率和两国食品价格都有变化：世界银行“一人一天最低成本健康饮食”的中国 ÷ 美国（按当年汇率）从 2021 年的 {fmt(cohdTrend.r21, 2)} 变为 {cohdTrend.last} 年的 {fmt(cohdTrend.rLast, 2)}；ICP 没有 2021 年之后的逐项比价。</>}
        </div>
      )}
      <div className="card">
        <div className="legend">
          <span><span className="sw" style={{ background: "var(--div-neg)" }} />比美国便宜</span>
          <span><span className="sw" style={{ background: "var(--div-mid)", border: "1px solid var(--axis)" }} />与美国相当</span>
          <span><span className="sw" style={{ background: "var(--div-pos)" }} />比美国贵</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <div style={{ minWidth: 980 }}>
            <Chart option={option} height={Math.max(220, isos.length * 26 + 60)} ariaLabel="各经济体分类价格水平热力图（美国=1）" />
          </div>
        </div>
        <p className="note">
          列名：居民消费＝居民最终消费整体；食品饮料＝食品与非酒精饮料；住房水电＝住房、水、电、燃气及其他燃料。
          ICP 按统一产品规格逐项比价，是比较各国“同样东西卖多少钱”的官方依据；这里展示的是 2021 年基准年的价格结构。
          2021 年之后各国物价和汇率都有变化，不宜把这张表直接当作今天的精确价差（今天的整体物价水平见上一节“相当于在美国花多少美元”，那是世界银行按年外推的官方数）。
        </p>
      </div>
    </section>
  );
}
