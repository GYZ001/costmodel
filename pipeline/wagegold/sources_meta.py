"""Human-facing description of every publisher, keyed by snapshot-key prefix."""

SOURCES = [
    {
        "prefix": "worldbank/CMO-Historical-Data-Monthly",
        "publisher": "世界银行（World Bank）",
        "title": "Commodity Price Data（Pink Sheet）月度价格：黄金",
        "landing": "https://www.worldbank.org/en/research/commodity-markets",
        "license": "CC BY 4.0",
        "use": "国际金价（美元/金衡盎司，月均）。按工作簿“Description”页：2025 年 6 月起为现货日价均值，此前为伦敦下午定盘价均值。",
    },
    {
        "prefix": "imf/",
        "publisher": "国际货币基金组织（IMF）",
        "title": "Primary Commodity Price System（PCPS）：PGOLD",
        "landing": "https://data.imf.org/en/datasets/IMF.RES:PCPS",
        "license": "IMF 数据使用条款（注明来源）",
        "use": "金价交叉核对（不直接用于计算）",
    },
    {
        "prefix": "worldbank/wdi_",
        "publisher": "世界银行（World Bank）",
        "title": "World Development Indicators：官方汇率、居民消费 PPP、人口；GDP 与居民消费的本币、美元、国际元值",
        "landing": "https://data.worldbank.org/",
        "license": "CC BY 4.0",
        "use": "各国年均官方汇率（PA.NUS.FCRF）、居民消费购买力平价（PA.NUS.PRVT.PP）、人口；GDP（NY.GDP.MKTP.CN/.CD）与居民消费（NE.CON.PRVT.CN/.PP.CD）只用于逐年核对汇率和购买力平价的货币单位",
    },
    {
        "prefix": "worldbank/fpn_",
        "publisher": "世界银行（World Bank）/ 联合国粮农组织（FAO）",
        "title": "Food Prices for Nutrition：健康饮食成本（CoHD）",
        "landing": "https://api.worldbank.org/v2/sources/88",
        "license": "CC BY 4.0",
        "use": "各国一人一天“最低成本健康饮食”的本币价格及六类食物分项",
    },
    {
        "prefix": "worldbank/icp2021_",
        "publisher": "世界银行（World Bank）",
        "title": "International Comparison Program 2021：分类价格水平",
        "landing": "https://api.worldbank.org/v2/sources/90",
        "license": "CC BY 4.0",
        "use": "2021 年基准年各类消费品（食品、住房、医疗、餐饮等）的价格水平，按统一规格比价",
    },
    {
        "prefix": "worldbank/countries",
        "publisher": "世界银行（World Bank）",
        "title": "经济体名录（中英文名称、地区、收入组）",
        "landing": "https://api.worldbank.org/v2/country",
        "license": "CC BY 4.0",
        "use": "国家名称与分组",
    },
    {
        "prefix": "worldbank/commodity_markets_landing",
        "publisher": "世界银行（World Bank）",
        "title": "Commodity Markets 页面（用于定位当月工作簿链接）",
        "landing": "https://www.worldbank.org/en/research/commodity-markets",
        "license": "—",
        "use": "仅用于找到最新 Pink Sheet 文件地址",
    },
    {
        "prefix": "ilostat/",
        "publisher": "国际劳工组织（ILO）",
        "title": "ILOSTAT：雇员平均/中位时薪与月薪（本币、美元、PPP 三种值）、每周实际工时",
        "landing": "https://ilostat.ilo.org/data/",
        "license": "CC BY 4.0",
        "use": "跨国工资与工时（男女合计）；ILOSTAT 自己的美元与 PPP 换算值用于核对本币值的货币单位，每条记录的注释决定其口径",
    },
    {
        "prefix": "oecd/",
        "publisher": "经济合作与发展组织（OECD）",
        "title": "OECD Data Explorer：平均年薪（全职当量；现价与不变价，本币与 PPP 美元）、全职雇员通常周工时",
        "landing": "https://data-explorer.oecd.org/",
        "license": "CC BY 4.0",
        "use": "OECD 数据库中经济体的工资水平与时薪折算；不变价本币与 PPP 美元两行用于核对本币值的货币单位",
    },
    {
        "prefix": "bls/",
        "publisher": "美国劳工统计局（BLS）",
        "title": "Public Data API v2：CES 平均时薪/工时、CPI 平均价格（AP）",
        "landing": "https://www.bls.gov/developers/",
        "license": "美国政府公共领域",
        "use": "美国月度时薪（1964 年起）与常见商品平均价格",
    },
    {
        "prefix": "fred/",
        "publisher": "圣路易斯联储（FRED）",
        "title": "FRED：BLS 时薪转载、美联储 H.10 月均汇率",
        "landing": "https://fred.stlouisfed.org/",
        "license": "数据来自 BLS 与美联储理事会（公共领域）",
        "use": "交叉核对（不直接用于计算）",
    },
    {
        "prefix": "ecb/",
        "publisher": "欧洲中央银行（ECB）",
        "title": "Euro foreign exchange reference rates（EXR）月均",
        "landing": "https://data.ecb.europa.eu/data/datasets/EXR",
        "license": "注明来源可自由使用",
        "use": "月度汇率与交叉核对",
    },
    {
        "prefix": "nbs/",
        "publisher": "国家统计局",
        "title": "数据发布：城镇单位平均工资、农民工监测调查报告、月度国民经济运行（企业周平均工作时间）、居民消费价格",
        "landing": "https://www.stats.gov.cn/sj/zxfb/",
        "license": "国家统计局网站（注明来源）",
        "use": "中国工资、农民工收入与调查工时；CPI 同比原句（用于核对相关说法）",
    },
]


def describe(manifest: dict) -> list[dict]:
    out = []
    for src in SOURCES:
        snaps = [dict(key=k, **{f: v[f] for f in ("url", "path", "retrieved_at", "sha256", "bytes", "status", "error")})
                 for k, v in sorted(manifest.items()) if k.startswith(src["prefix"])]
        if snaps:
            out.append({**src, "snapshots": snaps})
    return out
