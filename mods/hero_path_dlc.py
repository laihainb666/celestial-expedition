# -*- coding: utf-8 -*-
"""
《勇者之路·远征》V5 官方 DLC 扩展包
====================================
MOD_DLC = True  -> 主程序 V5 以 [DLC] 方式加载，内容标记 dlc 来源
含：全新勇者装备、试炼精英怪、DLC 终极 BOSS「深渊勇主·寂灭」、
勇者试炼事件，以及给 V5 AI 的 DLC 攻坚目标（BOSS 战清单）。
"""
MOD_NAME = "勇者之路·远征DLC"
MOD_DLC = True
MOD_VERSION = "1.0.0"

# ---------- DLC 专属装备（武器/护甲/饰品） ----------
MOD_ITEMS = {
    "v5hero_sword": {
        "name": "黎明誓约之剑",
        "type": "weapon",
        "atk": 320, "def": 0, "hp": 0, "crit": 0.12, "agi": 0, "dodge": 0,
        "price": 3800, "desc": "勇者之路DLC·勇者誓约铸造，破晓之光辉",
    },
    "v5hero_armor": {
        "name": "远征英魂战甲",
        "type": "armor",
        "atk": 10, "def": 280, "hp": 900, "crit": 0.0, "agi": 0, "dodge": 0.05,
        "price": 4200, "desc": "勇者之路DLC·历代英魂加持的远征战甲",
    },
    "v5hero_trinket": {
        "name": "勇者纹章·星坠",
        "type": "accessory",
        "atk": 60, "def": 20, "hp": 300, "crit": 0.08, "agi": 10, "dodge": 0.03,
        "price": 3600, "desc": "勇者之路DLC·代表远征荣耀的星坠纹章",
    },
    "v5hero_elixir": {
        "name": "远征圣泉药剂",
        "type": "potion", "heal": 2500, "mana": 150,
        "price": 800, "desc": "勇者之路DLC·圣泉炼制，回复 2500 HP",
    },
}

# ---------- DLC 专属怪物 / 精英 / BOSS ----------
MOD_MONSTERS = [
    {
        "name": "试炼石傀儡",
        "hp": 3200, "atk": 200, "def": 120, "exp": 900, "gold": 480,
        "zone_idx": [29], "boss": False,
        "desc": "勇者之路DLC·守望试炼之门的远古傀儡",
    },
    {
        "name": "幻影剑卫",
        "hp": 2600, "atk": 260, "def": 80, "exp": 820, "gold": 420,
        "zone_idx": [29], "boss": False,
        "desc": "勇者之路DLC·来自历代勇者试炼的幻影剑卫",
    },
    {
        "name": "霜语魔女",
        "hp": 3800, "atk": 240, "def": 100, "exp": 1100, "gold": 560,
        "zone_idx": [29], "boss": False,
        "desc": "勇者之路DLC·冻结试炼之地的霜语魔女",
    },
    {
        "name": "精英·屠龙者残魂",
        "hp": 9000, "atk": 330, "def": 160, "exp": 3600, "gold": 1500,
        "zone_idx": [29], "boss": False,
        "desc": "勇者之路DLC·曾在屠龙之战陨落的精英残魂",
    },
    {
        "name": "深渊勇主·寂灭",
        "hp": 52000, "atk": 480, "def": 240, "exp": 20000, "gold": 8888,
        "zone_idx": [29], "boss": True,
        "desc": "勇者之路DLC·最终 BOSS，深渊勇主的寂灭形态",
    },
]

# ---------- DLC 试炼事件 ----------
MOD_EVENTS = [
    {"text": "你踏入勇者试炼之地，刻满历代勇者铭文的石壁上浮现一行字：『唯有心怀黎明者，可执誓约之剑』。获得 300 金币与 1 瓶远征圣泉药剂。"},
    {"text": "试炼场的古老雕像突然裂开，一把闪耀的「黎明誓约之剑」悬浮在你面前。传说品质锻造材料散落一地，获得 500 经验。"},
    {"text": "深渊勇主的低语在试炼之地回荡：『放弃吧，凡人。』你握紧武器，决心回应这场宿命之战。"},
]

# ---------- V5 AI 攻坚目标（DLC BOSS 清单，供 ai_play_v5 战略决策） ----------
DLC_BOSS_NAMES = ["深渊勇主·寂灭"]
DLC_REQUIRED_LEVEL = 90   # AI 达到该等级后开始挑战 DLC 最终 BOSS
