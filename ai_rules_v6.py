# -*- coding: utf-8 -*-
"""
苍穹远征 V6 AI 策略规则库（自动生成，勿手改）
矩阵维度：职业(9) x 等级段(20) x 局势(8)。
ai_play_v6 按玩家职业/等级/血线/经济查询动作权重，进行加权决策。
"""

LEVEL_CAP = 200

# ---------------- 职业风格基准 ----------------
CLASS_STYLE = {
    '战士': {'upgrade': 10, 'buy': 6, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 4, 'explore': 3, 'task': 2},
    '法师': {'upgrade': 8, 'buy': 7, 'boss': 6, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 3, 'task': 3},
    '游侠': {'upgrade': 9, 'buy': 6, 'boss': 6, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 4, 'task': 3},
    '骑士': {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 8, 'craft': 4, 'explore': 2, 'task': 3},
    '刺客': {'upgrade': 11, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 4, 'craft': 5, 'explore': 4, 'task': 2},
    '牧师': {'upgrade': 7, 'buy': 7, 'boss': 5, 'advance': 4, 'rest': 9, 'craft': 6, 'explore': 3, 'task': 3},
    '术士': {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 6, 'explore': 3, 'task': 2},
    '武僧': {'upgrade': 10, 'buy': 5, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 4, 'task': 2},
    '召唤师': {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 3, 'task': 3},
}

# ---------------- 等级段修正曲线 ----------------
LEVEL_TABLE = {
    1: ((1, 10, {'upgrade': 3, 'buy': 2, 'explore': 1})),  # Lv1-10
    2: ((11, 20, {'upgrade': 3, 'buy': 2, 'boss': 1})),  # Lv11-20
    3: ((21, 30, {'upgrade': 1, 'buy': 2, 'boss': 2, 'advance': 1})),  # Lv21-30
    4: ((31, 40, {'buy': 1, 'boss': 2, 'advance': 2, 'craft': 1})),  # Lv31-40
    5: ((41, 50, {'boss': 2, 'advance': 2, 'craft': 1, 'task': 1})),  # Lv41-50
    6: ((51, 60, {'boss': 2, 'advance': 1, 'craft': 2, 'task': 1})),  # Lv51-60
    7: ((61, 70, {'boss': 1, 'advance': 1, 'craft': 2, 'task': 2})),  # Lv61-70
    8: ((71, 80, {'advance': 1, 'craft': 2, 'task': 2, 'explore': 1})),  # Lv71-80
    9: ((81, 90, {'craft': 2, 'task': 2, 'explore': 1, 'boss': 1})),  # Lv81-90
    10: ((91, 100, {'craft': 1, 'task': 2, 'explore': 2, 'boss': 1})),  # Lv91-100
    11: ((101, 110, {'task': 2, 'explore': 1, 'craft': 1, 'boss': 1})),  # Lv101-110
    12: ((111, 120, {'task': 2, 'explore': 1, 'craft': 1, 'boss': 1})),  # Lv111-120
    13: ((121, 130, {'task': 1, 'explore': 2, 'craft': 1})),  # Lv121-130
    14: ((131, 140, {'task': 1, 'explore': 2, 'craft': 1})),  # Lv131-140
    15: ((141, 150, {'explore': 1, 'task': 1, 'craft': 1})),  # Lv141-150
    16: ((151, 160, {'explore': 1, 'task': 1, 'craft': 1})),  # Lv151-160
    17: ((161, 170, {'explore': 2, 'boss': 1, 'task': 1})),  # Lv161-170
    18: ((171, 180, {'explore': 2, 'boss': 1, 'task': 1})),  # Lv171-180
    19: ((181, 190, {'explore': 1, 'boss': 2, 'task': 1})),  # Lv181-190
    20: ((191, 200, {'explore': 1, 'boss': 2, 'task': 1})),  # Lv191-200
}

# ---------------- 局势说明 ----------------
ACTIONS = [
    ("upgrade", "练级战斗：在当前区域刷怪积累经验与金币"),
    ("buy", "购置装备：评估商店最佳装备并换上"),
    ("boss", "攻坚BOSS：针对当前区域守关BOSS发起挑战"),
    ("advance", "推进区域：满足等级门槛后前往下一区域"),
    ("rest", "休整补给：低血量时自动用药/原地恢复"),
    ("craft", "锻造强化：合成药水或强化装备"),
    ("explore", "游历探索：触发区域随机事件与奇遇"),
    ("task", "清任务/图鉴：处理支线、成就与收集目标"),
]

# ---------------- 完整决策矩阵 ----------------
# 结构: MATRIX[职业][等级段] = {局势: 权重}
MATRIX = {
    '战士': {
        # Lv1-10
        1: {'upgrade': 13, 'buy': 8, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 4, 'explore': 4, 'task': 2},
        # Lv11-20
        2: {'upgrade': 13, 'buy': 8, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 4, 'explore': 3, 'task': 2},
        # Lv21-30
        3: {'upgrade': 11, 'buy': 8, 'boss': 9, 'advance': 6, 'rest': 6, 'craft': 4, 'explore': 3, 'task': 2},
        # Lv31-40
        4: {'upgrade': 10, 'buy': 7, 'boss': 9, 'advance': 7, 'rest': 6, 'craft': 5, 'explore': 3, 'task': 2},
        # Lv41-50
        5: {'upgrade': 10, 'buy': 6, 'boss': 9, 'advance': 7, 'rest': 6, 'craft': 5, 'explore': 3, 'task': 3},
        # Lv51-60
        6: {'upgrade': 10, 'buy': 6, 'boss': 9, 'advance': 6, 'rest': 6, 'craft': 6, 'explore': 3, 'task': 3},
        # Lv61-70
        7: {'upgrade': 10, 'buy': 6, 'boss': 8, 'advance': 6, 'rest': 6, 'craft': 6, 'explore': 3, 'task': 4},
        # Lv71-80
        8: {'upgrade': 10, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 6, 'craft': 6, 'explore': 4, 'task': 4},
        # Lv81-90
        9: {'upgrade': 10, 'buy': 6, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 6, 'explore': 4, 'task': 4},
        # Lv91-100
        10: {'upgrade': 10, 'buy': 6, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 5, 'explore': 5, 'task': 4},
        # Lv101-110
        11: {'upgrade': 10, 'buy': 6, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 5, 'explore': 4, 'task': 4},
        # Lv111-120
        12: {'upgrade': 10, 'buy': 6, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 5, 'explore': 4, 'task': 4},
        # Lv121-130
        13: {'upgrade': 10, 'buy': 6, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 5, 'explore': 5, 'task': 3},
        # Lv131-140
        14: {'upgrade': 10, 'buy': 6, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 5, 'explore': 5, 'task': 3},
        # Lv141-150
        15: {'upgrade': 10, 'buy': 6, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 5, 'explore': 4, 'task': 3},
        # Lv151-160
        16: {'upgrade': 10, 'buy': 6, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 5, 'explore': 4, 'task': 3},
        # Lv161-170
        17: {'upgrade': 10, 'buy': 6, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 4, 'explore': 5, 'task': 3},
        # Lv171-180
        18: {'upgrade': 10, 'buy': 6, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 4, 'explore': 5, 'task': 3},
        # Lv181-190
        19: {'upgrade': 10, 'buy': 6, 'boss': 9, 'advance': 5, 'rest': 6, 'craft': 4, 'explore': 4, 'task': 3},
        # Lv191-200
        20: {'upgrade': 10, 'buy': 6, 'boss': 9, 'advance': 5, 'rest': 6, 'craft': 4, 'explore': 4, 'task': 3},
    },
    '法师': {
        # Lv1-10
        1: {'upgrade': 11, 'buy': 9, 'boss': 6, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 4, 'task': 3},
        # Lv11-20
        2: {'upgrade': 11, 'buy': 9, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 3, 'task': 3},
        # Lv21-30
        3: {'upgrade': 9, 'buy': 9, 'boss': 8, 'advance': 6, 'rest': 7, 'craft': 5, 'explore': 3, 'task': 3},
        # Lv31-40
        4: {'upgrade': 8, 'buy': 8, 'boss': 8, 'advance': 7, 'rest': 7, 'craft': 6, 'explore': 3, 'task': 3},
        # Lv41-50
        5: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 7, 'rest': 7, 'craft': 6, 'explore': 3, 'task': 4},
        # Lv51-60
        6: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 6, 'rest': 7, 'craft': 7, 'explore': 3, 'task': 4},
        # Lv61-70
        7: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 6, 'rest': 7, 'craft': 7, 'explore': 3, 'task': 5},
        # Lv71-80
        8: {'upgrade': 8, 'buy': 7, 'boss': 6, 'advance': 6, 'rest': 7, 'craft': 7, 'explore': 4, 'task': 5},
        # Lv81-90
        9: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 7, 'explore': 4, 'task': 5},
        # Lv91-100
        10: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 5, 'task': 5},
        # Lv101-110
        11: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 4, 'task': 5},
        # Lv111-120
        12: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 4, 'task': 5},
        # Lv121-130
        13: {'upgrade': 8, 'buy': 7, 'boss': 6, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 5, 'task': 4},
        # Lv131-140
        14: {'upgrade': 8, 'buy': 7, 'boss': 6, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 5, 'task': 4},
        # Lv141-150
        15: {'upgrade': 8, 'buy': 7, 'boss': 6, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 4, 'task': 4},
        # Lv151-160
        16: {'upgrade': 8, 'buy': 7, 'boss': 6, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 4, 'task': 4},
        # Lv161-170
        17: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 5, 'task': 4},
        # Lv171-180
        18: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 5, 'task': 4},
        # Lv181-190
        19: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 4, 'task': 4},
        # Lv191-200
        20: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 4, 'task': 4},
    },
    '游侠': {
        # Lv1-10
        1: {'upgrade': 12, 'buy': 8, 'boss': 6, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 5, 'task': 3},
        # Lv11-20
        2: {'upgrade': 12, 'buy': 8, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 4, 'task': 3},
        # Lv21-30
        3: {'upgrade': 10, 'buy': 8, 'boss': 8, 'advance': 7, 'rest': 5, 'craft': 4, 'explore': 4, 'task': 3},
        # Lv31-40
        4: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 8, 'rest': 5, 'craft': 5, 'explore': 4, 'task': 3},
        # Lv41-50
        5: {'upgrade': 9, 'buy': 6, 'boss': 8, 'advance': 8, 'rest': 5, 'craft': 5, 'explore': 4, 'task': 4},
        # Lv51-60
        6: {'upgrade': 9, 'buy': 6, 'boss': 8, 'advance': 7, 'rest': 5, 'craft': 6, 'explore': 4, 'task': 4},
        # Lv61-70
        7: {'upgrade': 9, 'buy': 6, 'boss': 7, 'advance': 7, 'rest': 5, 'craft': 6, 'explore': 4, 'task': 5},
        # Lv71-80
        8: {'upgrade': 9, 'buy': 6, 'boss': 6, 'advance': 7, 'rest': 5, 'craft': 6, 'explore': 5, 'task': 5},
        # Lv81-90
        9: {'upgrade': 9, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 6, 'explore': 5, 'task': 5},
        # Lv91-100
        10: {'upgrade': 9, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 6, 'task': 5},
        # Lv101-110
        11: {'upgrade': 9, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 5, 'task': 5},
        # Lv111-120
        12: {'upgrade': 9, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 5, 'task': 5},
        # Lv121-130
        13: {'upgrade': 9, 'buy': 6, 'boss': 6, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 6, 'task': 4},
        # Lv131-140
        14: {'upgrade': 9, 'buy': 6, 'boss': 6, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 6, 'task': 4},
        # Lv141-150
        15: {'upgrade': 9, 'buy': 6, 'boss': 6, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 5, 'task': 4},
        # Lv151-160
        16: {'upgrade': 9, 'buy': 6, 'boss': 6, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 5, 'task': 4},
        # Lv161-170
        17: {'upgrade': 9, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 6, 'task': 4},
        # Lv171-180
        18: {'upgrade': 9, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 6, 'task': 4},
        # Lv181-190
        19: {'upgrade': 9, 'buy': 6, 'boss': 8, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 5, 'task': 4},
        # Lv191-200
        20: {'upgrade': 9, 'buy': 6, 'boss': 8, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 5, 'task': 4},
    },
    '骑士': {
        # Lv1-10
        1: {'upgrade': 12, 'buy': 9, 'boss': 7, 'advance': 5, 'rest': 8, 'craft': 4, 'explore': 3, 'task': 3},
        # Lv11-20
        2: {'upgrade': 12, 'buy': 9, 'boss': 8, 'advance': 5, 'rest': 8, 'craft': 4, 'explore': 2, 'task': 3},
        # Lv21-30
        3: {'upgrade': 10, 'buy': 9, 'boss': 9, 'advance': 6, 'rest': 8, 'craft': 4, 'explore': 2, 'task': 3},
        # Lv31-40
        4: {'upgrade': 9, 'buy': 8, 'boss': 9, 'advance': 7, 'rest': 8, 'craft': 5, 'explore': 2, 'task': 3},
        # Lv41-50
        5: {'upgrade': 9, 'buy': 7, 'boss': 9, 'advance': 7, 'rest': 8, 'craft': 5, 'explore': 2, 'task': 4},
        # Lv51-60
        6: {'upgrade': 9, 'buy': 7, 'boss': 9, 'advance': 6, 'rest': 8, 'craft': 6, 'explore': 2, 'task': 4},
        # Lv61-70
        7: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 6, 'rest': 8, 'craft': 6, 'explore': 2, 'task': 5},
        # Lv71-80
        8: {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 6, 'rest': 8, 'craft': 6, 'explore': 3, 'task': 5},
        # Lv81-90
        9: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 8, 'craft': 6, 'explore': 3, 'task': 5},
        # Lv91-100
        10: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 8, 'craft': 5, 'explore': 4, 'task': 5},
        # Lv101-110
        11: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 8, 'craft': 5, 'explore': 3, 'task': 5},
        # Lv111-120
        12: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 8, 'craft': 5, 'explore': 3, 'task': 5},
        # Lv121-130
        13: {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 8, 'craft': 5, 'explore': 4, 'task': 4},
        # Lv131-140
        14: {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 8, 'craft': 5, 'explore': 4, 'task': 4},
        # Lv141-150
        15: {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 8, 'craft': 5, 'explore': 3, 'task': 4},
        # Lv151-160
        16: {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 8, 'craft': 5, 'explore': 3, 'task': 4},
        # Lv161-170
        17: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 8, 'craft': 4, 'explore': 4, 'task': 4},
        # Lv171-180
        18: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 8, 'craft': 4, 'explore': 4, 'task': 4},
        # Lv181-190
        19: {'upgrade': 9, 'buy': 7, 'boss': 9, 'advance': 5, 'rest': 8, 'craft': 4, 'explore': 3, 'task': 4},
        # Lv191-200
        20: {'upgrade': 9, 'buy': 7, 'boss': 9, 'advance': 5, 'rest': 8, 'craft': 4, 'explore': 3, 'task': 4},
    },
    '刺客': {
        # Lv1-10
        1: {'upgrade': 14, 'buy': 8, 'boss': 7, 'advance': 6, 'rest': 4, 'craft': 5, 'explore': 5, 'task': 2},
        # Lv11-20
        2: {'upgrade': 14, 'buy': 8, 'boss': 8, 'advance': 6, 'rest': 4, 'craft': 5, 'explore': 4, 'task': 2},
        # Lv21-30
        3: {'upgrade': 12, 'buy': 8, 'boss': 9, 'advance': 7, 'rest': 4, 'craft': 5, 'explore': 4, 'task': 2},
        # Lv31-40
        4: {'upgrade': 11, 'buy': 7, 'boss': 9, 'advance': 8, 'rest': 4, 'craft': 6, 'explore': 4, 'task': 2},
        # Lv41-50
        5: {'upgrade': 11, 'buy': 6, 'boss': 9, 'advance': 8, 'rest': 4, 'craft': 6, 'explore': 4, 'task': 3},
        # Lv51-60
        6: {'upgrade': 11, 'buy': 6, 'boss': 9, 'advance': 7, 'rest': 4, 'craft': 7, 'explore': 4, 'task': 3},
        # Lv61-70
        7: {'upgrade': 11, 'buy': 6, 'boss': 8, 'advance': 7, 'rest': 4, 'craft': 7, 'explore': 4, 'task': 4},
        # Lv71-80
        8: {'upgrade': 11, 'buy': 6, 'boss': 7, 'advance': 7, 'rest': 4, 'craft': 7, 'explore': 5, 'task': 4},
        # Lv81-90
        9: {'upgrade': 11, 'buy': 6, 'boss': 8, 'advance': 6, 'rest': 4, 'craft': 7, 'explore': 5, 'task': 4},
        # Lv91-100
        10: {'upgrade': 11, 'buy': 6, 'boss': 8, 'advance': 6, 'rest': 4, 'craft': 6, 'explore': 6, 'task': 4},
        # Lv101-110
        11: {'upgrade': 11, 'buy': 6, 'boss': 8, 'advance': 6, 'rest': 4, 'craft': 6, 'explore': 5, 'task': 4},
        # Lv111-120
        12: {'upgrade': 11, 'buy': 6, 'boss': 8, 'advance': 6, 'rest': 4, 'craft': 6, 'explore': 5, 'task': 4},
        # Lv121-130
        13: {'upgrade': 11, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 4, 'craft': 6, 'explore': 6, 'task': 3},
        # Lv131-140
        14: {'upgrade': 11, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 4, 'craft': 6, 'explore': 6, 'task': 3},
        # Lv141-150
        15: {'upgrade': 11, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 4, 'craft': 6, 'explore': 5, 'task': 3},
        # Lv151-160
        16: {'upgrade': 11, 'buy': 6, 'boss': 7, 'advance': 6, 'rest': 4, 'craft': 6, 'explore': 5, 'task': 3},
        # Lv161-170
        17: {'upgrade': 11, 'buy': 6, 'boss': 8, 'advance': 6, 'rest': 4, 'craft': 5, 'explore': 6, 'task': 3},
        # Lv171-180
        18: {'upgrade': 11, 'buy': 6, 'boss': 8, 'advance': 6, 'rest': 4, 'craft': 5, 'explore': 6, 'task': 3},
        # Lv181-190
        19: {'upgrade': 11, 'buy': 6, 'boss': 9, 'advance': 6, 'rest': 4, 'craft': 5, 'explore': 5, 'task': 3},
        # Lv191-200
        20: {'upgrade': 11, 'buy': 6, 'boss': 9, 'advance': 6, 'rest': 4, 'craft': 5, 'explore': 5, 'task': 3},
    },
    '牧师': {
        # Lv1-10
        1: {'upgrade': 10, 'buy': 9, 'boss': 5, 'advance': 4, 'rest': 9, 'craft': 6, 'explore': 4, 'task': 3},
        # Lv11-20
        2: {'upgrade': 10, 'buy': 9, 'boss': 6, 'advance': 4, 'rest': 9, 'craft': 6, 'explore': 3, 'task': 3},
        # Lv21-30
        3: {'upgrade': 8, 'buy': 9, 'boss': 7, 'advance': 5, 'rest': 9, 'craft': 6, 'explore': 3, 'task': 3},
        # Lv31-40
        4: {'upgrade': 7, 'buy': 8, 'boss': 7, 'advance': 6, 'rest': 9, 'craft': 7, 'explore': 3, 'task': 3},
        # Lv41-50
        5: {'upgrade': 7, 'buy': 7, 'boss': 7, 'advance': 6, 'rest': 9, 'craft': 7, 'explore': 3, 'task': 4},
        # Lv51-60
        6: {'upgrade': 7, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 9, 'craft': 8, 'explore': 3, 'task': 4},
        # Lv61-70
        7: {'upgrade': 7, 'buy': 7, 'boss': 6, 'advance': 5, 'rest': 9, 'craft': 8, 'explore': 3, 'task': 5},
        # Lv71-80
        8: {'upgrade': 7, 'buy': 7, 'boss': 5, 'advance': 5, 'rest': 9, 'craft': 8, 'explore': 4, 'task': 5},
        # Lv81-90
        9: {'upgrade': 7, 'buy': 7, 'boss': 6, 'advance': 4, 'rest': 9, 'craft': 8, 'explore': 4, 'task': 5},
        # Lv91-100
        10: {'upgrade': 7, 'buy': 7, 'boss': 6, 'advance': 4, 'rest': 9, 'craft': 7, 'explore': 5, 'task': 5},
        # Lv101-110
        11: {'upgrade': 7, 'buy': 7, 'boss': 6, 'advance': 4, 'rest': 9, 'craft': 7, 'explore': 4, 'task': 5},
        # Lv111-120
        12: {'upgrade': 7, 'buy': 7, 'boss': 6, 'advance': 4, 'rest': 9, 'craft': 7, 'explore': 4, 'task': 5},
        # Lv121-130
        13: {'upgrade': 7, 'buy': 7, 'boss': 5, 'advance': 4, 'rest': 9, 'craft': 7, 'explore': 5, 'task': 4},
        # Lv131-140
        14: {'upgrade': 7, 'buy': 7, 'boss': 5, 'advance': 4, 'rest': 9, 'craft': 7, 'explore': 5, 'task': 4},
        # Lv141-150
        15: {'upgrade': 7, 'buy': 7, 'boss': 5, 'advance': 4, 'rest': 9, 'craft': 7, 'explore': 4, 'task': 4},
        # Lv151-160
        16: {'upgrade': 7, 'buy': 7, 'boss': 5, 'advance': 4, 'rest': 9, 'craft': 7, 'explore': 4, 'task': 4},
        # Lv161-170
        17: {'upgrade': 7, 'buy': 7, 'boss': 6, 'advance': 4, 'rest': 9, 'craft': 6, 'explore': 5, 'task': 4},
        # Lv171-180
        18: {'upgrade': 7, 'buy': 7, 'boss': 6, 'advance': 4, 'rest': 9, 'craft': 6, 'explore': 5, 'task': 4},
        # Lv181-190
        19: {'upgrade': 7, 'buy': 7, 'boss': 7, 'advance': 4, 'rest': 9, 'craft': 6, 'explore': 4, 'task': 4},
        # Lv191-200
        20: {'upgrade': 7, 'buy': 7, 'boss': 7, 'advance': 4, 'rest': 9, 'craft': 6, 'explore': 4, 'task': 4},
    },
    '术士': {
        # Lv1-10
        1: {'upgrade': 12, 'buy': 9, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 6, 'explore': 4, 'task': 2},
        # Lv11-20
        2: {'upgrade': 12, 'buy': 9, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 6, 'explore': 3, 'task': 2},
        # Lv21-30
        3: {'upgrade': 10, 'buy': 9, 'boss': 9, 'advance': 6, 'rest': 6, 'craft': 6, 'explore': 3, 'task': 2},
        # Lv31-40
        4: {'upgrade': 9, 'buy': 8, 'boss': 9, 'advance': 7, 'rest': 6, 'craft': 7, 'explore': 3, 'task': 2},
        # Lv41-50
        5: {'upgrade': 9, 'buy': 7, 'boss': 9, 'advance': 7, 'rest': 6, 'craft': 7, 'explore': 3, 'task': 3},
        # Lv51-60
        6: {'upgrade': 9, 'buy': 7, 'boss': 9, 'advance': 6, 'rest': 6, 'craft': 8, 'explore': 3, 'task': 3},
        # Lv61-70
        7: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 6, 'rest': 6, 'craft': 8, 'explore': 3, 'task': 4},
        # Lv71-80
        8: {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 6, 'rest': 6, 'craft': 8, 'explore': 4, 'task': 4},
        # Lv81-90
        9: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 8, 'explore': 4, 'task': 4},
        # Lv91-100
        10: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 7, 'explore': 5, 'task': 4},
        # Lv101-110
        11: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 7, 'explore': 4, 'task': 4},
        # Lv111-120
        12: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 7, 'explore': 4, 'task': 4},
        # Lv121-130
        13: {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 7, 'explore': 5, 'task': 3},
        # Lv131-140
        14: {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 7, 'explore': 5, 'task': 3},
        # Lv141-150
        15: {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 7, 'explore': 4, 'task': 3},
        # Lv151-160
        16: {'upgrade': 9, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 6, 'craft': 7, 'explore': 4, 'task': 3},
        # Lv161-170
        17: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 6, 'explore': 5, 'task': 3},
        # Lv171-180
        18: {'upgrade': 9, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 6, 'craft': 6, 'explore': 5, 'task': 3},
        # Lv181-190
        19: {'upgrade': 9, 'buy': 7, 'boss': 9, 'advance': 5, 'rest': 6, 'craft': 6, 'explore': 4, 'task': 3},
        # Lv191-200
        20: {'upgrade': 9, 'buy': 7, 'boss': 9, 'advance': 5, 'rest': 6, 'craft': 6, 'explore': 4, 'task': 3},
    },
    '武僧': {
        # Lv1-10
        1: {'upgrade': 13, 'buy': 7, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 5, 'task': 2},
        # Lv11-20
        2: {'upgrade': 13, 'buy': 7, 'boss': 8, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 4, 'task': 2},
        # Lv21-30
        3: {'upgrade': 11, 'buy': 7, 'boss': 9, 'advance': 7, 'rest': 5, 'craft': 4, 'explore': 4, 'task': 2},
        # Lv31-40
        4: {'upgrade': 10, 'buy': 6, 'boss': 9, 'advance': 8, 'rest': 5, 'craft': 5, 'explore': 4, 'task': 2},
        # Lv41-50
        5: {'upgrade': 10, 'buy': 5, 'boss': 9, 'advance': 8, 'rest': 5, 'craft': 5, 'explore': 4, 'task': 3},
        # Lv51-60
        6: {'upgrade': 10, 'buy': 5, 'boss': 9, 'advance': 7, 'rest': 5, 'craft': 6, 'explore': 4, 'task': 3},
        # Lv61-70
        7: {'upgrade': 10, 'buy': 5, 'boss': 8, 'advance': 7, 'rest': 5, 'craft': 6, 'explore': 4, 'task': 4},
        # Lv71-80
        8: {'upgrade': 10, 'buy': 5, 'boss': 7, 'advance': 7, 'rest': 5, 'craft': 6, 'explore': 5, 'task': 4},
        # Lv81-90
        9: {'upgrade': 10, 'buy': 5, 'boss': 8, 'advance': 6, 'rest': 5, 'craft': 6, 'explore': 5, 'task': 4},
        # Lv91-100
        10: {'upgrade': 10, 'buy': 5, 'boss': 8, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 6, 'task': 4},
        # Lv101-110
        11: {'upgrade': 10, 'buy': 5, 'boss': 8, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 5, 'task': 4},
        # Lv111-120
        12: {'upgrade': 10, 'buy': 5, 'boss': 8, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 5, 'task': 4},
        # Lv121-130
        13: {'upgrade': 10, 'buy': 5, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 6, 'task': 3},
        # Lv131-140
        14: {'upgrade': 10, 'buy': 5, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 6, 'task': 3},
        # Lv141-150
        15: {'upgrade': 10, 'buy': 5, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 5, 'task': 3},
        # Lv151-160
        16: {'upgrade': 10, 'buy': 5, 'boss': 7, 'advance': 6, 'rest': 5, 'craft': 5, 'explore': 5, 'task': 3},
        # Lv161-170
        17: {'upgrade': 10, 'buy': 5, 'boss': 8, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 6, 'task': 3},
        # Lv171-180
        18: {'upgrade': 10, 'buy': 5, 'boss': 8, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 6, 'task': 3},
        # Lv181-190
        19: {'upgrade': 10, 'buy': 5, 'boss': 9, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 5, 'task': 3},
        # Lv191-200
        20: {'upgrade': 10, 'buy': 5, 'boss': 9, 'advance': 6, 'rest': 5, 'craft': 4, 'explore': 5, 'task': 3},
    },
    '召唤师': {
        # Lv1-10
        1: {'upgrade': 11, 'buy': 9, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 4, 'task': 3},
        # Lv11-20
        2: {'upgrade': 11, 'buy': 9, 'boss': 8, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 3, 'task': 3},
        # Lv21-30
        3: {'upgrade': 9, 'buy': 9, 'boss': 9, 'advance': 6, 'rest': 7, 'craft': 5, 'explore': 3, 'task': 3},
        # Lv31-40
        4: {'upgrade': 8, 'buy': 8, 'boss': 9, 'advance': 7, 'rest': 7, 'craft': 6, 'explore': 3, 'task': 3},
        # Lv41-50
        5: {'upgrade': 8, 'buy': 7, 'boss': 9, 'advance': 7, 'rest': 7, 'craft': 6, 'explore': 3, 'task': 4},
        # Lv51-60
        6: {'upgrade': 8, 'buy': 7, 'boss': 9, 'advance': 6, 'rest': 7, 'craft': 7, 'explore': 3, 'task': 4},
        # Lv61-70
        7: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 6, 'rest': 7, 'craft': 7, 'explore': 3, 'task': 5},
        # Lv71-80
        8: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 6, 'rest': 7, 'craft': 7, 'explore': 4, 'task': 5},
        # Lv81-90
        9: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 7, 'craft': 7, 'explore': 4, 'task': 5},
        # Lv91-100
        10: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 5, 'task': 5},
        # Lv101-110
        11: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 4, 'task': 5},
        # Lv111-120
        12: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 4, 'task': 5},
        # Lv121-130
        13: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 5, 'task': 4},
        # Lv131-140
        14: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 5, 'task': 4},
        # Lv141-150
        15: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 4, 'task': 4},
        # Lv151-160
        16: {'upgrade': 8, 'buy': 7, 'boss': 7, 'advance': 5, 'rest': 7, 'craft': 6, 'explore': 4, 'task': 4},
        # Lv161-170
        17: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 5, 'task': 4},
        # Lv171-180
        18: {'upgrade': 8, 'buy': 7, 'boss': 8, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 5, 'task': 4},
        # Lv181-190
        19: {'upgrade': 8, 'buy': 7, 'boss': 9, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 4, 'task': 4},
        # Lv191-200
        20: {'upgrade': 8, 'buy': 7, 'boss': 9, 'advance': 5, 'rest': 7, 'craft': 5, 'explore': 4, 'task': 4},
    },
}

# ---------------- 危险局势覆盖 ----------------
# 血线 < 40% 时无条件放大休整权重（避免送死）
DANGER_OVERRIDE = {'upgrade': 0, 'buy': 0, 'boss': 0, 'advance': 0, 'rest': 60, 'craft': 0, 'explore': 0, 'task': 0}

# ---------------- 经济局势覆盖 ----------------
# 金币富余(> 等级*180) 时放大买装权重
RICH_OVERRIDE = {'buy': +6, 'upgrade': -2, 'explore': +1}

# 决战阶段：满级后专注 全BOSS讨伐 / DLC攻坚 / 任务收尾
ENDGAME_BIAS = {'boss': +4, 'task': +3, 'explore': +2, 'craft': +2, 'upgrade': 0, 'buy': 0}

# 区域推进门槛：低于门槛等级不过度追求立即推进（防御性策略）
ADVANCE_SAFETY_LEVEL = 3

# BOSS 挑战前最低血量门槛（百分比）
BOSS_MIN_HP_RATIO = 0.55

# 目标区域推荐：等级 -> 建议 zone 索引
ZONE_RECOMMEND = [
    (1, 0),  # Lv1 建议推进到第 1 区
    (3, 1),  # Lv3 建议推进到第 2 区
    (5, 2),  # Lv5 建议推进到第 3 区
    (8, 3),  # Lv8 建议推进到第 4 区
    (12, 4),  # Lv12 建议推进到第 5 区
    (16, 5),  # Lv16 建议推进到第 6 区
    (20, 6),  # Lv20 建议推进到第 7 区
    (25, 7),  # Lv25 建议推进到第 8 区
    (30, 8),  # Lv30 建议推进到第 9 区
    (35, 9),  # Lv35 建议推进到第 10 区
    (40, 10),  # Lv40 建议推进到第 11 区
    (45, 11),  # Lv45 建议推进到第 12 区
    (50, 12),  # Lv50 建议推进到第 13 区
    (55, 13),  # Lv55 建议推进到第 14 区
    (60, 14),  # Lv60 建议推进到第 15 区
    (65, 15),  # Lv65 建议推进到第 16 区
    (70, 16),  # Lv70 建议推进到第 17 区
    (75, 17),  # Lv75 建议推进到第 18 区
    (80, 18),  # Lv80 建议推进到第 19 区
    (85, 19),  # Lv85 建议推进到第 20 区
    (90, 20),  # Lv90 建议推进到第 21 区
    (95, 21),  # Lv95 建议推进到第 22 区
    (100, 22),  # Lv100 建议推进到第 23 区
    (105, 23),  # Lv105 建议推进到第 24 区
    (110, 24),  # Lv110 建议推进到第 25 区
    (115, 25),  # Lv115 建议推进到第 26 区
    (120, 26),  # Lv120 建议推进到第 27 区
    (125, 27),  # Lv125 建议推进到第 28 区
    (130, 28),  # Lv130 建议推进到第 29 区
    (140, 29),  # Lv140 建议推进到第 30 区
]

# 战斗内技能优先级（随等级解锁变化，按索引引用 SKILLS 表）
SKILL_PRIORITY = {
    1: [0, 1],
    3: [0, 1, 2],
    5: [0, 2, 3],
    8: [1, 2, 3, 4],
    12: [2, 3, 4, 5],
    18: [3, 4, 5, 6],
    25: [4, 5, 6, 7],
    35: [5, 6, 7, 8],
    50: [6, 7, 8, 9],
    70: [7, 8, 9, 10],
    90: [8, 9, 10, 11],
    120: [9, 10, 11],
    160: [10, 11],
    190: [11],
}

# 存档策略：越往后自动存档越频繁，防止长时间运行丢档
SAVE_STRATEGY = {
    1: 50,   # 前期每 50 回合存档
    2: 20,   # 中期每 20 回合存档
    3: 10,   # 后期每 10 回合存档
    4: 5,    # 决战期每 5 回合存档
}

# 回合节奏：每 N 回合深度维护（买装+清包+合成）
MAINTENANCE_INTERVAL = 20

# AI 内部状态展示字段名（用于 --report 与 MCP status 查询）
REPORT_FIELDS = ['level', 'zone', 'gold', 'kills', 'boss_kills', 'pet', 'round']

AI_RULES_VERSION = "v5.0.0"
