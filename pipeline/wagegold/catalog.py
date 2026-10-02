"""Static reference facts used for labelling only (never for selecting or excluding data)."""

# G20 members (19 countries; the EU and the African Union are members as blocs).
G20 = {"ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "IDN", "ITA", "JPN", "KOR", "MEX", "RUS",
       "SAU", "ZAF", "TUR", "GBR", "USA"}

# U.S. CPI average-price items: label, BLS unit, and factor converting the BLS unit to the display unit.
LB_TO_KG = 1 / 0.45359237
US_ITEMS = {
    "flour": ("面粉（白面粉，通用）", "每磅", "kg", LB_TO_KG),
    "rice": ("大米（白米，长粒，生）", "每磅", "kg", LB_TO_KG),
    "pasta": ("意面与通心粉", "每磅", "kg", LB_TO_KG),
    "bread_white": ("白面包（切片）", "每磅", "kg", LB_TO_KG),
    "ground_beef": ("牛肉馅（100% 牛肉）", "每磅", "kg", LB_TO_KG),
    "sirloin_steak": ("西冷牛排（USDA Choice，去骨）", "每磅", "kg", LB_TO_KG),
    "bacon": ("培根（切片）", "每磅", "kg", LB_TO_KG),
    "chicken_whole": ("整鸡（鲜）", "每磅", "kg", LB_TO_KG),
    "chicken_breast": ("鸡胸肉（去骨）", "每磅", "kg", LB_TO_KG),
    "eggs": ("鸡蛋（A 级，大号）", "每打（12 个）", "dozen", 1.0),
    "milk_whole": ("全脂鲜牛奶", "每加仑（3.785 升）", "L", 1 / 3.785411784),
    "cheddar": ("切达奶酪", "每磅", "kg", LB_TO_KG),
    "butter": ("黄油（条装）", "每磅", "kg", LB_TO_KG),
    "bananas": ("香蕉", "每磅", "kg", LB_TO_KG),
    "oranges": ("橙子（脐橙）", "每磅", "kg", LB_TO_KG),
    "potatoes": ("土豆（白）", "每磅", "kg", LB_TO_KG),
    "lettuce": ("生菜（球生菜）", "每磅", "kg", LB_TO_KG),
    "tomatoes": ("番茄（大田种植）", "每磅", "kg", LB_TO_KG),
    "sugar": ("白砂糖", "每磅", "kg", LB_TO_KG),
    "coffee": ("咖啡粉（100%，烘焙研磨）", "每磅", "kg", LB_TO_KG),
    "gasoline": ("汽油（普通无铅）", "每加仑", "L", 1 / 3.785411784),
    "electricity": ("居民电价", "每千瓦时", "kWh", 1.0),
}
