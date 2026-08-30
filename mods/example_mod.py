# -*- coding: utf-8 -*-
"""
示例模组：演示 v3.0 模组系统（模块化架构）
在 mods/ 目录放置 .py 文件，定义以下变量即可自动加载：
  MOD_NAME      : 模组名称
  MOD_ITEMS     : dict {item_id: {name, type, desc, ...}}
  MOD_MONSTERS  : list [{name, hp, atk, def, exp, gold, ...}]
  MOD_EVENTS    : list [{id, text, ...}]
启动游戏或读档时自动扫描加载（D 调试台 -> mod_reload 可重载）。
"""

MOD_NAME = "星尘拓展包"

MOD_ITEMS = {
    "mod_star_blade": {
        "name": "星尘之刃",
        "type": "weapon",
        "desc": "由模组添加的传说武器，剑身流转星尘。",
    },
    "mod_star_cloak": {
        "name": "星尘斗篷",
        "type": "armor",
        "desc": "由模组添加的护甲，抵御暗影侵蚀。",
    },
    "mod_star_ring": {
        "name": "星尘戒指",
        "type": "trinket",
        "desc": "由模组添加的饰品，蕴含星辰之力。",
    },
}

MOD_MONSTERS = [
    {
        "name": "星尘傀儡",
        "hp": 260,
        "atk": 22,
        "def": 10,
        "exp": 55,
        "gold": 40,
        "desc": "由模组添加的机械造物。",
    },
    {
        "name": "裂隙主宰",
        "hp": 900,
        "atk": 45,
        "def": 24,
        "exp": 220,
        "gold": 180,
        "boss": True,
        "desc": "由模组添加的 BOSS，镇守时空裂隙。",
    },
]

MOD_EVENTS = [
    {
        "id": "mod_star_shower",
        "text": "星尘如雨般洒落，你沐浴其中，感到力量涌动。",
    },
    {
        "id": "mod_rift_call",
        "text": "一道时空裂隙在你面前展开，传来低沉的呼唤。",
    },
]
