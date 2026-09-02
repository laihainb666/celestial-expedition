# -*- coding: utf-8 -*-
"""
模组：AI 接入
================================================
AI 主题内容扩展：
  - 3 件 AI 智能装备
  - 3 只 AI 机械怪物（含 1 BOSS）
  - 3 个 AI 剧情事件
启动游戏或读档时自动扫描加载。
可与主程序 /ai 命令、ai_generate 接口配合使用。
"""

MOD_NAME = "AI接入"

MOD_ITEMS = {
    "ai_neural_blade": {
        "name": "神经脉冲刃",
        "type": "weapon",
        "atk": 42,
        "crit": 0.05,
        "price": 700,
        "desc": "搭载神经网络的智能武器，可根据战斗实时调整攻击轨迹。",
    },
    "ai_matrix_armor": {
        "name": "矩阵护甲",
        "type": "armor",
        "def": 30,
        "agi": 4,
        "price": 660,
        "desc": "由数字矩阵编织的护甲，可预判敌人攻击路径。",
    },
    "ai_core": {
        "name": "智能核心",
        "type": "accessory",
        "atk": 10,
        "def": 8,
        "agi": 5,
        "price": 720,
        "desc": "凝聚 AI 算力的核心晶体，佩戴者思维如电。",
    },
}

MOD_MONSTERS = [
    {
        "name": "巡逻无人机",
        "hp": 300,
        "atk": 30,
        "def": 12,
        "exp": 80,
        "gold": 60,
        "desc": "在废墟上空巡逻的智能无人机，双目射出红光。",
    },
    {
        "name": "机械守卫",
        "hp": 520,
        "atk": 40,
        "def": 22,
        "exp": 130,
        "gold": 100,
        "desc": "守护数据中心的重型机械守卫。",
    },
    {
        "name": "失控 AI 主脑",
        "hp": 1500,
        "atk": 58,
        "def": 32,
        "exp": 380,
        "gold": 320,
        "boss": True,
        "desc": "觉醒自我意识后失控的 AI 主脑，统领着所有机械。",
    },
]

MOD_EVENTS = [
    {
        "id": "ai_transmission",
        "text": "空中传来断断续续的电子讯号，似乎在向你求救。",
    },
    {
        "id": "ai_database",
        "text": "你闯入一间废弃机房，屏幕上流动着看不懂的代码洪流。",
    },
    {
        "id": "ai_awaken",
        "text": "一具机械残骸突然亮起指示灯，发出沙哑的声音：'带我走吧……'",
    },
]
