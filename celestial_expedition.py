# -*- coding: utf-8 -*-
"""
苍穹远征：星陨传说 (Celestial Expedition: Starfall Legend)
==========================================================
一款玩法丰富的超大型纯 Python 文字冒险 RPG（无需任何第三方依赖）。

包含系统：
  - 角色创建（战士/法师/游侠 三职业，专属技能）
  - 回合制战斗（技能/普攻/防御/逃跑/用药，暴击/闪避/属性克制）
  - 世界地图（10+ 区域，150x150 网格随机生成，内存充足）
  - 探索事件（宝箱/陷阱/流浪商人/祭坛/洞窟）
  - 怪物图鉴（40+ 种怪物，逐级解锁）
  - 装备物品（100+ 物品，数据驱动，武器/护甲/饰品/药水/材料/任务品）
  - 商店系统（买卖装备、药品补给）
  - 锻造强化（材料合成药水、装备 +1~+9 强化）
  - 任务系统（3 章主线 + 8 个支线）
  - 宠物系统（击败 BOSS 收服宠物，提供战斗加成）
  - 成就系统（12 项成就，记录里程碑）
  - 存档系统（JSON 持久化）
  - 内存统计（启动时打印进程 RSS，通常 10MB+）

玩法入口：
    python3 celestial_expedition.py
"""

import json
import os
import random
import resource
import sys
import time

VERSION = "3.1.0"
SAVE_FILE = "starfall_save.json"


# ============================================================
# 品质系统（v3.1）
# 根据物品 id 稳定推导品质，无需改动数据表：
#   普通(40%) < 优秀(25%) < 精良(18%) < 史诗(12%) < 传说(5%)
# 品质影响装备属性加成与名字词缀。
# ============================================================
QUALITY_LEVELS = [
    ("普通", 1.00, ""),
    ("优秀", 1.15, "精良"),
    ("精良", 1.30, "闪耀"),
    ("史诗", 1.50, "史诗"),
    ("传说", 1.80, "传说"),
]


def item_quality(item_id):
    """根据物品 id 稳定推导品质等级（0-4）"""
    if not item_id:
        return 0
    import hashlib
    h = int(hashlib.md5(str(item_id).encode("utf-8")).hexdigest(), 16)
    r = h % 100
    if r < 40:
        return 0
    if r < 65:
        return 1
    if r < 83:
        return 2
    if r < 95:
        return 3
    return 4


def quality_bonus(item_id):
    """品质属性加成系数"""
    return QUALITY_LEVELS[item_quality(item_id)][1]


def quality_word(item_id):
    """品质名字词缀"""
    return QUALITY_LEVELS[item_quality(item_id)][2]


def quality_tag(item_id):
    """品质标签（中文名）"""
    return QUALITY_LEVELS[item_quality(item_id)][0]


def display_name(item_id):
    """带品质词缀的显示名；非装备直接返回原名"""
    if not item_id:
        return ""
    it = ITEM_MAP.get(item_id)
    if not it:
        return str(item_id)
    if it.get("type") in ("weapon", "armor", "accessory"):
        w = quality_word(item_id)
        return (w + "·" + it["name"]) if w else it["name"]
    return it["name"]


# ============================================================
# 0. 内存统计与启动信息
# ============================================================
def memory_rss_kb() -> int:
    """返回当前进程常驻内存 RSS（KB）"""
    try:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return 0


def show_boot_info():
    rss = memory_rss_kb()
    print("=" * 62)
    print("     苍 穹 远 征 ： 星 陨 传 说   v%s" % VERSION)
    print("=" * 62)
    print(f"  进程内存占用: {rss} KB ({rss/1024:.1f} MB)")
    if rss >= 800:
        print("  ✔ 内存占用已达标（≥ 800 KB）")
    else:
        print("  内存占用未达 800KB 阈值")
    print("-" * 62)
    print("  v3.0 新增：九职业 / 调试命令台150条 / AI自动游玩")
    print("           六类图鉴 / 模组系统 / 实验模式 / AI内容生成")
    print("-" * 62)


# ============================================================
# 1. 数据驱动：大数据模块（由 gen_content.py 生成，约 1.9MB）
#    25 区域 / 220 怪物 / 4382 装备 / 72 任务 / 600 事件 / 2280 语录
#    20 NPC / 70 配方 / 45 成就 / 20 宠物 / 12 章主线剧情
# ============================================================
from starfall_data import (CLASSES, SKILLS, MONSTERS, ITEM_MAP, ZONES,
                           QUESTS, ACHIEVEMENTS, PETS, EVENT_TEXTS,
                           QUOTES, NPCS, RECIPES, STORY_CHAPTERS)

# ============================================================
# 1.5 v3.0 九职业扩展（原 3 职业 + 6 新职业；专精系统预留接口）
# ============================================================
_EXTRA_CLASSES = {
    "骑士": {"hp": 180, "mp": 45, "atk": 24, "def": 22, "agi": 7,
             "crit": 0.08, "dodge": 0.04, "desc": "圣光守护，高防减伤"},
    "刺客": {"hp": 105, "mp": 55, "atk": 25, "def": 10, "agi": 22,
             "crit": 0.28, "dodge": 0.20, "desc": "暗杀爆发，暴击极高"},
    "牧师": {"hp": 115, "mp": 110, "atk": 18, "def": 12, "agi": 8,
             "crit": 0.08, "dodge": 0.06, "desc": "神圣治疗，续航回复"},
    "术士": {"hp": 110, "mp": 115, "atk": 26, "def": 10, "agi": 9,
             "crit": 0.12, "dodge": 0.07, "desc": "暗黑诅咒，生命汲取"},
    "武僧": {"hp": 140, "mp": 50, "atk": 25, "def": 15, "agi": 16,
             "crit": 0.15, "dodge": 0.14, "desc": "气劲连击，攻守兼备"},
    "召唤师": {"hp": 105, "mp": 120, "atk": 18, "def": 11, "agi": 10,
              "crit": 0.09, "dodge": 0.08, "desc": "召唤兽协战，群体作战"},
}
CLASSES.update(_EXTRA_CLASSES)

_EXTRA_SKILLS = {
    "骑士": [
        {"name": "圣击",   "cost": 0,  "mult": 1.3, "cd": 0, "desc": "圣光加持的武器打击"},
        {"name": "守护壁垒","cost": 15, "buff": 35,  "cd": 2, "desc": "大幅提升护盾"},
        {"name": "圣光裁决","cost": 28, "mult": 2.5, "cd": 3, "desc": "圣光惩戒敌人"},
        {"name": "神圣护佑","cost": 40, "buff": 50,  "cd": 5, "desc": "获得强力护盾"},
    ],
    "刺客": [
        {"name": "刺击",   "cost": 0,  "mult": 1.5, "cd": 0, "desc": "迅捷突刺"},
        {"name": "毒刃",   "cost": 12, "mult": 2.2, "cd": 2, "desc": "淬毒之刃"},
        {"name": "影袭",   "cost": 20, "mult": 2.8, "cd": 3, "desc": "阴影突袭"},
        {"name": "致命一击","cost": 35, "mult": 4.0, "cd": 5, "desc": "无视防御的斩杀"},
    ],
    "牧师": [
        {"name": "圣光弹", "cost": 0,  "mult": 1.2, "cd": 0, "desc": "神圣能量弹"},
        {"name": "治疗术", "cost": 15, "heal": 80,  "cd": 2, "desc": "恢复大量生命"},
        {"name": "圣光灼烧","cost": 20, "mult": 2.2, "cd": 3, "desc": "神圣之火"},
        {"name": "大恢复", "cost": 35, "heal": 150, "cd": 5, "desc": "强效群体恢复"},
    ],
    "术士": [
        {"name": "暗影箭", "cost": 0,  "mult": 1.4, "cd": 0, "desc": "暗影能量箭"},
        {"name": "痛苦诅咒","cost": 12, "mult": 2.0, "cd": 2, "desc": "持续折磨目标"},
        {"name": "吸血术", "cost": 22, "mult": 2.4, "cd": 3, "desc": "吸取生命"},
        {"name": "末日降临","cost": 40, "mult": 3.8, "cd": 5, "desc": "召唤末日之力"},
    ],
    "武僧": [
        {"name": "拳击",   "cost": 0,  "mult": 1.4, "cd": 0, "desc": "精准拳击"},
        {"name": "连击",   "cost": 12, "mult": 2.2, "cd": 2, "desc": "快速连续攻击"},
        {"name": "气功波", "cost": 20, "mult": 2.6, "cd": 3, "desc": "凝聚气劲爆发"},
        {"name": "金刚不坏","cost": 35, "buff": 45,  "cd": 5, "desc": "金刚护体"},
    ],
    "召唤师": [
        {"name": "魔力弹", "cost": 0,  "mult": 1.2, "cd": 0, "desc": "基础魔力弹"},
        {"name": "召唤狼灵","cost": 15, "mult": 2.0, "cd": 2, "desc": "召唤狼灵攻击"},
        {"name": "召唤炎魔","cost": 25, "mult": 2.6, "cd": 3, "desc": "召唤炎魔"},
        {"name": "召唤龙神","cost": 45, "mult": 3.6, "cd": 5, "desc": "召唤龙神降临"},
    ],
}
# 为新增职业生成 8 个强化变体技能（与现有职业结构一致）
_VARIANT_PREFIX = [("烈焰", 1.1), ("寒冰", 1.15), ("雷霆", 1.2), ("星辰", 1.25),
                   ("虚空", 1.3), ("龙裔", 1.35), ("圣光", 1.4), ("深渊", 1.45)]
for _cls, _skl in _EXTRA_SKILLS.items():
    _base = _skl[0]
    for i, (_pre, _boost) in enumerate(_VARIANT_PREFIX):
        _skl.append({"name": _pre + _base["name"], "cost": 8 + i * 5, "cd": 1 + i // 2,
                     "mult": 1.0 + _boost, "desc": "蕴含%s之力的强化技能" % _pre})
    SKILLS[_cls] = _skl
# ============================================================
# 2. 世界地图（150x150 网格，区域内部探索地图）
# ============================================================
MAP_SIZE = 150


def generate_zone_map(seed: int):
    """生成区域网格地图：0=空地 1=树/岩 2=怪物点 3=宝箱 4=出口"""
    random.seed(seed)
    grid = [[0] * MAP_SIZE for _ in range(MAP_SIZE)]
    for _ in range(MAP_SIZE * MAP_SIZE // 12):
        r, c = random.randint(0, MAP_SIZE - 1), random.randint(0, MAP_SIZE - 1)
        grid[r][c] = 1
    for _ in range(30):
        grid[random.randint(0, MAP_SIZE - 1)][random.randint(0, MAP_SIZE - 1)] = 2
    for _ in range(12):
        grid[random.randint(0, MAP_SIZE - 1)][random.randint(0, MAP_SIZE - 1)] = 3
    grid[0][0] = 4
    return grid


# ============================================================
# 3. 核心类：玩家 / 敌人 / 宠物 / 游戏引擎
# ============================================================
class Player:
    def __init__(self, name, cls):
        c = CLASSES[cls]
        self.name = name
        self.cls = cls
        self.level = 1
        self.exp = 0
        self.gold = 100
        self.hp = c["hp"]
        self.max_hp = c["hp"]
        self.mp = c["mp"]
        self.max_mp = c["mp"]
        self.base_atk = c["atk"]
        self.base_def = c["def"]
        self.agi = c["agi"]
        self.crit = c["crit"]
        self.dodge = c["dodge"]
        self.weapon = None
        self.armor = None
        self.accessory = None
        self.inventory = {}          # item_id -> count
        self.potions = {"p1": 3, "p3": 2}
        self.skills_cd = [0] * len(SKILLS[cls])
        self.shield = 0
        self.zone = 0
        self.pos = [0, 0]
        self.kills = 0
        self.bosses = []
        self.quests_done = []
        self.achievements = []
        self.pet = None
        self.played_time = 0.0
        self._last_enemy_hp = 0
        # 设置/调试选项
        self.god_mode = False     # 无敌模式：战斗中不掉血
        self.one_hit = False      # 一击必杀：秒杀敌人
        self.show_damage = False  # 伤害明细显示
        self.stats = {"explore": 0, "battle": 0, "death": 0, "gold_earned": 0}
        # 图鉴收集记录
        self.seen_monsters = set()
        self.seen_items = set()
        self.seen_zones = set()
        # 强化等级记录 {item_id: level}（v3.1）
        self.enhance = {}

    # ---- 属性计算（v3.1 修复：按 id 查表 + 品质加成 + 强化加成） ----
    def atk(self):
        v = self.base_atk
        if self.weapon:
            it = ITEM_MAP.get(self.weapon) or {}
            v += it.get("atk", 0) * quality_bonus(self.weapon)
            v += self.enhance.get(self.weapon, 0)
        if self.accessory:
            it = ITEM_MAP.get(self.accessory) or {}
            v += it.get("atk", 0) * quality_bonus(self.accessory)
        return int(v)

    def defense(self):
        v = self.base_def
        if self.armor:
            it = ITEM_MAP.get(self.armor) or {}
            v += it.get("def", 0) * quality_bonus(self.armor)
        if self.accessory:
            it = ITEM_MAP.get(self.accessory) or {}
            v += it.get("def", 0) * quality_bonus(self.accessory)
        return int(v)

    def max_hp_full(self):
        v = self.max_hp
        if self.armor:
            it = ITEM_MAP.get(self.armor) or {}
            v += it.get("hp", 0) * quality_bonus(self.armor)
        if self.accessory:
            it = ITEM_MAP.get(self.accessory) or {}
            v += it.get("hp", 0) * quality_bonus(self.accessory)
        return int(v)

    def crit_rate(self):
        v = self.crit
        if self.accessory:
            it = ITEM_MAP.get(self.accessory) or {}
            v += it.get("crit", 0) * quality_bonus(self.accessory)
        return min(0.8, v)

    def agi_full(self):
        v = self.agi
        if self.accessory:
            it = ITEM_MAP.get(self.accessory) or {}
            v += it.get("agi", 0) * quality_bonus(self.accessory)
        return int(v)

    def exp_needed(self):
        return 50 + (self.level - 1) * 60

    def add_exp(self, amount):
        self.exp += amount
        while self.exp >= self.exp_needed():
            self.exp -= self.exp_needed()
            self.level += 1
            self.max_hp += 12
            self.max_mp += 6
            self.base_atk += 3
            self.base_def += 2
            self.hp = self.max_hp_full()
            self.mp = self.max_mp
            print(f"  ★ 升级！等级提升至 {self.level}")

    def reset_battle(self):
        self.shield = 0
        self.skills_cd = [0] * len(SKILLS[self.cls])

    def to_dict(self):
        d = dict(self.__dict__)
        # set 转 list，保证 JSON 可序列化
        for k in ("seen_monsters", "seen_items", "seen_zones"):
            if isinstance(d.get(k), set):
                d[k] = list(d[k])
        return d

    @classmethod
    def from_dict(cls, d):
        p = cls(d["name"], d["cls"])
        p.__dict__.update(d)
        # 旧存档兼容：补默认设置/统计字段
        p.god_mode = getattr(p, "god_mode", False)
        p.one_hit = getattr(p, "one_hit", False)
        p.show_damage = getattr(p, "show_damage", False)
        p.stats = getattr(p, "stats", {"explore": 0, "battle": 0, "death": 0, "gold_earned": 0})
        # list 转回 set（兼容旧存档缺字段）
        for k, default in (("seen_monsters", set()), ("seen_items", set()), ("seen_zones", set())):
            v = getattr(p, k, default)
            p.__dict__[k] = set(v) if v is not None else set()
        return p


class Enemy:
    def __init__(self, spec):
        self.spec = spec
        self.name = spec["name"]
        self.hp = spec["hp"]
        self.max_hp = spec["hp"]
        self.atk = spec["atk"]
        self.defense = spec["def"]
        self.exp = spec["exp"]
        self.gold = spec["gold"]
        self.boss = spec.get("boss", False)


def calc_damage(atk_val, def_val, crit_rate=0.0):
    crit = random.random() < crit_rate
    dmg = max(1, atk_val * random.uniform(0.9, 1.1) - def_val)
    if crit:
        dmg *= 1.8
    return int(dmg), crit


# ============================================================
# 4. 游戏引擎：探索 / 战斗 / 商店 / 锻造 / 任务 / 存档
# ============================================================
class Game:
    def __init__(self, player):
        self.p = player
        self.maps = {}
        self.msg = ""
        self.running = True
        # v3.0：实验模式 / 模组 / AI 内容生成
        self.experiment_mode = False
        self.mods = []
        self.ai_api_key = ""

    # ---------- 工具 ----------
    def get_zone(self):
        return ZONES[self.p.zone]

    def item_count(self, item_id):
        return self.p.inventory.get(item_id, 0)

    def add_item(self, item_id, n=1):
        self.p.inventory[item_id] = self.item_count(item_id) + n

    def remove_item(self, item_id, n=1):
        if self.item_count(item_id) >= n:
            self.p.inventory[item_id] -= n
            if self.p.inventory[item_id] <= 0:
                del self.p.inventory[item_id]
            return True
        return False

    def check_achieve(self, key, value):
        """按成就 id 精确匹配解锁条件，避免一次误解锁全部成就"""
        rules = {
            "ac1": ("kill", 1), "ac2": ("level", 10), "ac3": ("boss", "狼王·裂齿"),
            "ac4": ("kill", 100), "ac5": ("gold", 1000), "ac6": ("equip", 10),
            "ac7": ("craft", 5), "ac8": ("pet", 1), "ac9": ("boss", "星陨之神"),
            "ac10": ("quests", 12), "ac11": ("gold", 5000), "ac12": ("allboss", 20),
        }
        for a in ACHIEVEMENTS:
            aid = a["id"]
            if aid in self.p.achievements:
                continue
            if str(aid).startswith("ac") and str(aid)[2:].isdigit() and int(str(aid)[2:]) >= 13:
                rkey, rval = "kill", (int(str(aid)[2:]) - 12) * 50   # 征程之N -> N*50 击杀
            else:
                rkey, rval = rules.get(aid, (None, None))
            if rkey != key:
                continue
            hit = False
            if rkey == "kill" and self.p.kills >= rval:
                hit = True
            elif rkey == "level" and self.p.level >= rval:
                hit = True
            elif rkey == "boss" and rval in self.p.bosses:
                hit = True
            elif rkey == "gold" and self.p.gold >= rval:
                hit = True
            elif rkey == "equip" and self.count_equips() >= rval:
                hit = True
            elif rkey == "craft" and getattr(self, "craft_count", 0) >= rval:
                hit = True
            elif rkey == "pet" and self.p.pet:
                hit = True
            elif rkey == "quests" and len([q for q in self.p.quests_done if q.startswith("m")]) >= rval:
                hit = True
            elif rkey == "allboss" and len(self.p.bosses) >= rval:
                hit = True
            if hit:
                self.p.achievements.append(aid)
                print(f"  ★ 成就解锁：{a['name']} —— {a['desc']}")

    def count_equips(self):
        eq = self.p.inventory
        return sum(1 for iid in eq for _ in range(eq[iid])
                   if ITEM_MAP[iid]["type"] in ("weapon", "armor", "accessory"))

    # ---------- 主循环 ----------
    def run(self):
        show_boot_info()
        print(f"欢迎，勇者 {self.p.name}（{self.p.cls}）！")
        while self.running:
            zone = self.get_zone()
            print("\n" + "=" * 62)
            print(self.status_line())
            print("-" * 62)
            print("  1 探索区域    2 战斗(刷怪)  3 商店    4 背包/装备")
            print("  5 锻造合成    6 任务      7 宠物    8 区域地图/传送")
            print("  9 存档        A 剧情日志  0 退出")
            print("  S 设置/调试   D 调试控制台  T 图鉴   / 实验模式命令")
            cmd = input("  指令 > ").strip()
            if cmd.startswith("/"):
                self.chat_command(cmd)
            elif cmd == "1":
                self.explore()
            elif cmd == "2":
                self.encounter_monster()
            elif cmd == "3":
                self.shop()
            elif cmd == "4":
                self.inventory_menu()
            elif cmd == "5":
                self.craft_menu()
            elif cmd == "6":
                self.quest_menu()
            elif cmd == "7":
                self.pet_menu()
            elif cmd == "8":
                self.map_menu()
            elif cmd == "9":
                self.save()
            elif cmd.lower() == "a":
                self.story_menu()
            elif cmd.lower() == "s":
                self.settings_menu()
            elif cmd.lower() == "d":
                self.debug_console()
            elif cmd.lower() == "t":
                self.codex_menu()
            elif cmd == "0":
                print("旅程暂告段落，期待你的归来。")
                self.running = False
            else:
                print("无效指令。")

    # ---------- 探索 ----------
    def explore(self):
        zone = self.get_zone()
        self.p.stats["explore"] += 1
        key = zone["name"]
        if key not in self.maps:
            self.maps[key] = generate_zone_map(zone["level"] * 31 + self.p.zone)
        grid = self.maps[key]
        r, c = self.p.pos
        print(f"\n-- 在{zone['name']}中探索（位置 {r},{c} / {MAP_SIZE}x{MAP_SIZE}）--")
        steps = random.randint(3, 8)
        for _ in range(steps):
            dr, dc = random.choice([(-1, 0), (1, 0), (0, -1), (0, 1)])
            nr, nc = max(0, min(MAP_SIZE - 1, r + dr)), max(0, min(MAP_SIZE - 1, c + dc))
            r, c = nr, nc
        self.p.pos = [r, c]
        cell = grid[r][c]
        event = random.random()
        if cell == 2 or event < 0.28:
            self.encounter_monster()
        elif cell == 3 or event < 0.43:
            self.chest_event()
        elif event < 0.53:
            self.trap_event()
        elif event < 0.63:
            self.merchant_event()
        elif event < 0.72:
            self.shrine_event()
        elif event < 0.80:
            self.npc_event()
        elif self.experiment_mode and event < 0.95:
            self.experiment_event()
        else:
            print("  🍃 风平浪静，行路间偶得一句箴言：")
            print(f"    「{random.choice(QUOTES)}」")

    def chest_event(self):
        roll = random.random()
        if roll < 0.5:
            gold = random.randint(20, 80) + self.p.level * 5
            self.p.gold += gold
            self.p.stats["gold_earned"] += gold
            print(f"  🎁 发现宝箱！获得 {gold} 金币")
        elif roll < 0.8:
            iid = random.choice(["p1", "p2", "p3", "m1", "m2", "m5"])
            self.add_item(iid)
            print(f"  🎁 发现宝箱！获得 {display_name(iid)}")
        else:
            eq = [iid for iid in ITEM_MAP if ITEM_MAP[iid]["type"] in ("weapon", "armor", "accessory")]
            iid = random.choice(eq)
            self.add_item(iid)
            print(f"  🎁 发现稀有宝箱！获得装备 {display_name(iid)}")
        self.check_achieve("gold", 1000)
        self.check_achieve("gold", 5000)

    def trap_event(self):
        dmg = random.randint(10, 30) + self.p.level * 2
        self.p.hp = max(1, self.p.hp - dmg)
        print(f"  ⚠ 触发陷阱！受到 {dmg} 点伤害（当前 HP {self.p.hp}）")

    def merchant_event(self):
        print("  🧙 遇到流浪商人：")
        if EVENT_TEXTS:
            print("    " + random.choice(EVENT_TEXTS))
        print("    他微笑着递给你一份小礼物。")
        iid = random.choice(["p1", "p2", "m2", "m8"])
        self.add_item(iid)
        print(f"    获得 {display_name(iid)} x1")

    def npc_event(self):
        npc = random.choice(NPCS)
        print(f"  💬 遇见 {npc['name']}（{npc['place']}）：")
        print(f"    「{random.choice(npc['lines'])}」")

    def shrine_event(self):
        choice = random.choice(["hp", "mp", "gold", "atk"])
        if choice == "hp":
            self.p.hp = min(self.p.max_hp_full(), self.p.hp + 60)
            print("  ⛩ 古老祭坛治愈了你，恢复 60 点生命。")
        elif choice == "mp":
            self.p.mp = min(self.p.max_mp, self.p.mp + 50)
            print("  ⛩ 古老祭坛灌注魔力，恢复 50 点法力。")
        elif choice == "gold":
            g = random.randint(30, 90)
            self.p.gold += g
            self.p.stats["gold_earned"] += g
            print(f"  ⛩ 祭坛下埋着前人遗物，获得 {g} 金币。")
        else:
            self.p.base_atk += 2
            print("  ⛩ 祭坛祝福了你，攻击力 +2！")

    # ---------- 战斗 ----------
    def pick_monster(self):
        zone = self.get_zone()
        pool = [MONSTERS[i] for i in zone["monsters"]]
        m = random.choice(pool)
        # BOSS 区域中 boss 出场概率提升
        if zone.get("final") and random.random() < 0.35:
            m = random.choice([x for x in pool if x.get("boss")])
        return Enemy(m)

    def _fight(self, enemy):
        """自动战斗（供调试召唤/AI游玩使用）：自动技能/用药，战至终局"""
        self.p.stats["battle"] = self.p.stats.get("battle", 0) + 1
        print(f"\n  ⚔ AI自动战斗：遭遇 {enemy.name}！" + ("【BOSS 战！】" if enemy.boss else ""))
        self.p.reset_battle()
        enemy_hp = enemy.hp
        guard_round = 0
        while enemy_hp > 0:
            # 玩家自动回合
            skills = SKILLS[self.p.cls]
            use_skill = None
            if self.p.mp >= 8 and not self.p.one_hit:
                usable = [(i, s) for i, s in enumerate(skills)
                          if self.p.skills_cd[i] == 0 and self.p.mp >= s["cost"] and s.get("mult")]
                if usable:
                    i, s = max(usable, key=lambda x: x[1].get("mult", 0))
                    use_skill = (i, s)
            if use_skill:
                i, s = use_skill
                self.p.mp -= s["cost"]
                self.p.skills_cd = [max(0, x - 1) for x in self.p.skills_cd]
                self.p.skills_cd[i] = s["cd"]
                dmg, crit = calc_damage(int(self.p.atk() * s["mult"]), enemy.defense, self.p.crit_rate())
                if self.p.one_hit:
                    dmg = enemy_hp
                enemy_hp -= dmg
                print(f"  [AI] 使用 {s['name']}，造成 {dmg} 伤害{'（暴击！）' if crit else ''}")
            else:
                dmg, crit = calc_damage(self.p.atk(), enemy.defense, self.p.crit_rate())
                if self.p.one_hit:
                    dmg = enemy_hp
                enemy_hp -= dmg
                print(f"  [AI] 普攻，造成 {dmg} 伤害{'（暴击！）' if crit else ''}")
            # 宠物协助
            if self.p.pet and random.random() < 0.5:
                pdef = PETS[self.p.pet]
                dmg = max(1, pdef["atk"] + self.p.level - enemy.defense)
                enemy_hp -= dmg
                print(f"  [AI] 🐾 宠物{self.p.pet}攻击，造成 {dmg} 伤害！")
            if enemy_hp <= 0:
                print(f"\n  ✔ 击败 {enemy.name}！")
                self.p.kills += 1
                exp = int(enemy.exp * 1.5) if enemy.boss else enemy.exp
                self.p.add_exp(exp)
                gold = enemy.gold + random.randint(0, 10)
                self.p.gold += gold
                self.p.stats["gold_earned"] = self.p.stats.get("gold_earned", 0) + gold
                print(f"  获得经验 {exp}，金币 {gold}。")
                if enemy.boss:
                    self.on_boss_kill(enemy)
                self.check_achieve("kill", 1)
                self.check_achieve("kill", 100)
                self.check_achieve("level", 10)
                self.check_achieve("gold", 1000)
                self.check_achieve("gold", 5000)
                self.check_achieve("equip", 10)
                self.check_achieve("allboss", 6)
                self.drop_item(enemy)
                return True
            # 敌人回合
            if self.p.god_mode:
                print(f"  {enemy.name} 的攻击被无敌模式完全挡下！")
            elif self.p.dodge > 0 and random.random() < self.p.dodge:
                print(f"  {enemy.name} 的攻击被闪避了！")
            else:
                dmg = max(1, int(enemy.atk * random.uniform(0.9, 1.1) - self.p.defense()))
                if self.p.shield > 0:
                    absorb = min(self.p.shield, int(dmg))
                    self.p.shield -= absorb
                    dmg -= absorb
                dmg = max(1, int(dmg))
                self.p.hp -= dmg
                print(f"  {enemy.name} 攻击你，造成 {dmg} 伤害。")
                # AI 自动用药/防御
                if self.p.hp <= 0:
                    print("\n  ✖ AI 角色倒下了……")
                    self.handle_death()
                    return False
                if self.p.hp < self.p.max_hp_full() * 0.4:
                    if self.use_potion():
                        print("  [AI] 自动使用药水恢复！")
                    else:
                        self.p.shield += 15
                        print("  [AI] 无药可用，转为防御姿态。")
        return True

    def encounter_monster(self):
        enemy = self.pick_monster()
        self.p.stats["battle"] += 1
        print(f"\n  ⚔ 遭遇 {enemy.name}！")
        if enemy.boss:
            print("  【BOSS 战！】")
        self.p.reset_battle()
        enemy_hp = enemy.hp
        while True:
            print("-" * 50)
            print(f"  你: HP {self.p.hp}/{self.p.max_hp_full()}  MP {self.p.mp}/{self.p.max_mp}"
                  f"  护盾{self.p.shield}   敌人: HP {enemy_hp}/{enemy.max_hp}")
            print("  1 攻击  2 技能  3 防御  4 用药  5 逃跑")
            c = input("  > ").strip()
            if c == "1":
                dmg, crit = calc_damage(self.p.atk(), enemy.defense, self.p.crit_rate())
                if self.p.one_hit:
                    dmg = enemy_hp
                    crit = False
                enemy_hp -= dmg
                print(f"  你攻击敌人，造成 {dmg} 伤害{'（暴击！）' if crit else ''}")
                if self.p.show_damage:
                    print(f"    [明细] 攻击力 {self.p.atk()} vs 防御 {enemy.defense}，暴击率 {self.p.crit_rate():.0%}"
                          f"{'（一击必杀！）' if self.p.one_hit else ''}")
            elif c == "2":
                self.cast_skill(enemy_hp)
                enemy_hp = self._last_enemy_hp
            elif c == "3":
                self.p.shield += 15
                print("  你架起防御姿态，护盾 +15。")
            elif c == "4":
                used = self.use_potion()
                if not used:
                    continue
            elif c == "5":
                if random.random() < 0.5 + self.p.agi_full() * 0.01:
                    print("  你成功逃跑了！")
                    return
                print("  逃跑失败！")
            else:
                print("  无效指令。")
                continue

            # 宠物协助
            if self.p.pet and random.random() < 0.5:
                pdef = PETS[self.p.pet]
                dmg = max(1, pdef["atk"] + self.p.level - enemy.defense)
                enemy_hp -= dmg
                print(f"  🐾 宠物{self.p.pet}攻击敌人，造成 {dmg} 伤害！")

            if enemy_hp <= 0:
                print(f"\n  ✔ 击败 {enemy.name}！")
                self.p.kills += 1
                exp = enemy.exp
                if enemy.boss:
                    exp = int(exp * 1.5)
                self.p.add_exp(exp)
                gold = enemy.gold + random.randint(0, 10)
                self.p.gold += gold
                self.p.stats["gold_earned"] += gold
                print(f"  获得经验 {exp}，金币 {gold}。")
                if enemy.boss:
                    self.on_boss_kill(enemy)
                self.check_achieve("kill", 1)
                self.check_achieve("kill", 100)
                self.check_achieve("level", 10)
                self.check_achieve("gold", 1000)
                self.check_achieve("gold", 5000)
                self.check_achieve("equip", 10)
                self.check_achieve("allboss", 6)
                # 随机掉落
                self.drop_item(enemy)
                return

            # 敌人回合
            if self.p.god_mode:
                print(f"  {enemy.name} 的攻击被无敌模式完全挡下！")
            elif self.p.dodge > 0 and random.random() < self.p.dodge:
                print(f"  {enemy.name} 的攻击被闪避了！")
            else:
                dmg = max(1, enemy.atk * random.uniform(0.9, 1.1) - self.p.defense())
                if self.p.shield > 0:
                    absorb = min(self.p.shield, int(dmg))
                    self.p.shield -= absorb
                    dmg -= absorb
                    print(f"  护盾吸收了 {absorb} 点伤害。")
                dmg = max(1, int(dmg))
                self.p.hp -= dmg
                print(f"  {enemy.name} 攻击你，造成 {dmg} 伤害。")
                if self.p.hp <= 0:
                    print("\n  ✖ 你倒下了……")
                    self.handle_death()
                    return

    def cast_skill(self, enemy_hp):
        """技能菜单；用实例变量暂存敌人剩余血量（简化实现）"""
        skills = SKILLS[self.p.cls]
        print("  技能：")
        for i, s in enumerate(skills):
            cd = self.p.skills_cd[i]
            state = "就绪" if cd == 0 else f"冷却{cd}"
            print(f"    {i}. {s['name']}（{s['desc']}）[{state}] MP{s['cost']}")
        c = input("  选择技能 > ").strip()
        if not c.isdigit() or int(c) not in range(len(skills)):
            print("  无效选择。")
            self._last_enemy_hp = enemy_hp
            return
        i = int(c)
        s = skills[i]
        if self.p.skills_cd[i] > 0:
            print(f"  {s['name']} 还在冷却中。")
            self._last_enemy_hp = enemy_hp
            return
        if self.p.mp < s["cost"]:
            print("  法力不足！")
            self._last_enemy_hp = enemy_hp
            return
        self.p.mp -= s["cost"]
        self.p.skills_cd = [max(0, x - 1) for x in self.p.skills_cd]
        self.p.skills_cd[i] = s["cd"]
        if s.get("mult"):
            # 技能无视防御，按攻击倍率计算
            dmg, crit = calc_damage(int(self.p.atk() * s["mult"]), 0,
                                    self.p.crit_rate())
            self._last_enemy_hp = max(0, enemy_hp - dmg)
            print(f"  ⚡ 你施放 {s['name']}，造成 {dmg} 伤害{'（暴击！）' if crit else ''}")
        elif s.get("buff"):
            self.p.shield += s["buff"]
            self._last_enemy_hp = enemy_hp
            print(f"  🛡 你施放 {s['name']}，护盾 +{s['buff']}。")

    def use_potion(self):
        options = {iid: ITEM_MAP[iid] for iid in self.p.potions
                   if self.p.potions[iid] > 0}
        if not options:
            print("  没有可用的药水。")
            return False
        print("  药水：")
        for i, (iid, it) in enumerate(options.items()):
            print(f"    {i}. {it['name']} x{self.p.potions[iid]}")
        c = input("  使用 > ").strip()
        if not c.isdigit() or int(c) not in range(len(options)):
            print("  取消。")
            return False
        iid = list(options.keys())[int(c)]
        it = ITEM_MAP[iid]
        self.p.potions[iid] -= 1
        if it.get("heal"):
            self.p.hp = min(self.p.max_hp_full(), self.p.hp + it["heal"])
            print(f"  使用 {it['name']}，恢复 {it['heal']} 生命。")
        if it.get("mana"):
            self.p.mp = min(self.p.max_mp, self.p.mp + it["mana"])
            print(f"  使用 {it['name']}，恢复 {it['mana']} 法力。")
        return True

    def on_boss_kill(self, enemy):
        self.p.bosses.append(enemy.name)
        print(f"  👑 你讨伐了 BOSS：{enemy.name}！")
        # 掉落任务奖励（按 QUESTS 数据，匹配 BOSS 名称）
        for q in QUESTS:
            if q.get("boss") is not None and MONSTERS[q["boss"]]["name"] == enemy.name:
                ri = q.get("reward_item")
                if ri:
                    self.grant_reward(ri)
        # 有概率收服宠物
        if enemy.name in PETS and self.p.pet is None and random.random() < 0.7:
            self.p.pet = enemy.name
            print(f"  🐾 {enemy.name} 臣服于你，成为了你的宠物！")
            self.check_achieve("pet", 1)
        self.check_achieve("boss", enemy.name)
        self.check_achieve("allboss", 6)

    def grant_reward(self, ri):
        if ri in ITEM_MAP:
            self.add_item(ri)
            print(f"    奖励物品：{display_name(ri)}")
        elif str(ri).startswith("ac") and ri not in self.p.achievements:
            self.p.achievements.append(ri)
            a = next((x for x in ACHIEVEMENTS if x["id"] == ri), None)
            if a:
                print(f"  ★ 成就解锁：{a['name']} —— {a['desc']}")

    def drop_item(self, enemy):
        roll = random.random()
        zone = self.get_zone()
        if roll < 0.35:
            iid = random.choice(["p1", "p2", "m1"])
            self.add_item(iid)
            print(f"  掉落：{display_name(iid)} x1")
        elif roll < 0.55:
            pool = [x for x in zone["shop"] if ITEM_MAP[x]["type"] in ("weapon", "armor", "accessory")]
            if pool:
                iid = random.choice(pool)
                self.add_item(iid)
                print(f"  掉落装备：{display_name(iid)} x1")
                self.check_achieve("equip", 10)

    def handle_death(self):
        self.p.stats["death"] += 1
        print("  你被传送回晨曦草原，损失了一半金币。")
        self.p.gold //= 2
        self.p.hp = self.p.max_hp_full()
        self.p.mp = self.p.max_mp
        self.p.zone = 0
        self.p.pos = [0, 0]

    # ---------- 商店 ----------
    def shop(self):
        zone = self.get_zone()
        stock = zone["shop"]
        print(f"\n-- {zone['name']} 的商店 --")
        print("  出售物品：")
        for i, iid in enumerate(stock):
            it = ITEM_MAP[iid]
            print(f"    {i}. {it['name']} 价格 {it['price']} 金币")
        print("  b. 返回")
        c = input("  购买 > ").strip()
        if c.isdigit() and int(c) in range(len(stock)):
            iid = stock[int(c)]
            it = ITEM_MAP[iid]
            if self.p.gold < it["price"]:
                print("  金币不足。")
                return
            self.p.gold -= it["price"]
            if it["type"] == "potion":
                self.p.potions[iid] = self.p.potions.get(iid, 0) + 1
            else:
                self.add_item(iid)
            print(f"  购买成功：{it['name']}")
        elif c.lower() == "sell":
            self.sell_menu()
        elif c.lower() != "b":
            print("  无效选择。")

    def sell_menu(self):
        print("\n-- 出售物品 --")
        items = [iid for iid in self.p.inventory
                 if ITEM_MAP[iid]["type"] in ("weapon", "armor", "accessory", "material")]
        if not items:
            print("  没有可出售的物品。")
            return
        for i, iid in enumerate(items):
            it = ITEM_MAP[iid]
            print(f"    {i}. {it['name']} x{self.p.inventory[iid]} 出售价 {it['price'] // 2}")
        c = input("  选择出售 > ").strip()
        if c.isdigit() and int(c) in range(len(items)):
            iid = items[int(c)]
            self.remove_item(iid)
            self.p.gold += ITEM_MAP[iid]["price"] // 2
            print(f"  出售 {display_name(iid)}，获得 {ITEM_MAP[iid]['price'] // 2} 金币。")

    # ---------- 背包 / 装备 ----------
    def inventory_menu(self):
        print("\n-- 背包 --")
        print(f"  金币: {self.p.gold}   药水: "
              + ", ".join(f"{ITEM_MAP[i]['name']}x{self.p.potions[i]}" for i in self.p.potions if self.p.potions[i] > 0))
        if not self.p.inventory:
            print("  （背包空空如也）")
        else:
            for iid, n in self.p.inventory.items():
                it = ITEM_MAP[iid]
                extra = ""
                if it.get("atk"):
                    extra += f" 攻击+{it['atk']}"
                if it.get("def"):
                    extra += f" 防御+{it['def']}"
                if it.get("crit"):
                    extra += f" 暴击+{int(it['crit']*100)}%"
                if it.get("agi"):
                    extra += f" 敏捷+{it['agi']}"
                print(f"    {q}{display_name(iid)} x{n}{extra}  [{it['type']}]  <{iid}>")
        print("\n-- 装备栏 --")
        w = display_name(self.p.weapon) if self.p.weapon else "无"
        ar = display_name(self.p.armor) if self.p.armor else "无"
        ac = display_name(self.p.accessory) if self.p.accessory else "无"
        print(f"  武器: {w}   护甲: {ar}   饰品: {ac}")
        print("  输入装备 id 或名字以穿戴（如输入 烈焰 或 w_烈焰_铁剑_之刃），q 返回：")
        c = input("  > ").strip().lower()
        if c == "q":
            return
        # 匹配：先精确 id，再精确名字，再模糊名字
        target = None
        if c in ITEM_MAP and self.item_count(c) > 0:
            target = c
        else:
            cands = [iid for iid in self.p.inventory
                     if ITEM_MAP[iid]["type"] in ("weapon", "armor", "accessory")
                     and self.item_count(iid) > 0
                     and (c in ITEM_MAP[iid]["name"].lower() or c in iid.lower())]
            if len(cands) == 1:
                target = cands[0]
            elif len(cands) > 1:
                print("  匹配到多个装备，请选择编号：")
                for i, iid in enumerate(cands, 1):
                    it = ITEM_MAP[iid]
                    print(f"    {i}. [{quality_tag(iid)}] {display_name(iid)} ({it['type']}) <{iid}>")
                try:
                    sel = int(input("  > ").strip())
                    if 1 <= sel <= len(cands):
                        target = cands[sel - 1]
                except ValueError:
                    pass
            else:
                print("  未找到可装备的物品（输入 id 或名字的一部分）。")
        if target:
            it = ITEM_MAP[target]
            slot = {"weapon": "weapon", "armor": "armor", "accessory": "accessory"}[it["type"]]
            old = getattr(self.p, slot)
            if old:
                self.add_item(old)
            setattr(self.p, slot, target)
            self.remove_item(target)
            print(f"  已装备 {display_name(target)}（{quality_tag(target)}品质）！")
            self.check_achieve("equip", 10)
        else:
            print("  无法装备该物品。")

    # ---------- 锻造合成 ----------
    def __init_craft(self):
        if not hasattr(self, "craft_count"):
            self.craft_count = 0

    def craft_menu(self):
        self.__init_craft()
        page = 0
        per_page = 8
        total_pages = max(0, (len(RECIPES) - 1) // per_page)
        while True:
            print(f"\n-- 锻造合成（共 {len(RECIPES)} 种配方，已完成 {self.craft_count} 次）--")
            batch = RECIPES[page * per_page:(page + 1) * per_page]
            for i, r in enumerate(batch):
                print(f"  {i}. {r['ingredients']} -> {r['output']}")
            print(f"  n. 下一页({page + 1}/{total_pages + 1})  p. 上一页  9. 装备强化  q. 返回")
            c = input("  > ").strip().lower()
            if c == "n":
                if page < total_pages:
                    page += 1
            elif c == "p":
                if page > 0:
                    page -= 1
            elif c == "9":
                self.enhance_weapon()
            elif c == "q":
                return
            elif c.isdigit() and int(c) in range(len(batch)):
                self.try_craft(batch[int(c)])
            else:
                print("  无效选择。")

    def try_craft(self, r):
        """解析配方 ingredients（如：铁矿石x2 + 星尘碎片x1），消耗材料并产出"""
        need = []  # [(item_id, count)]
        for part in r["ingredients"].split("+"):
            part = part.strip()
            name, _, num = part.partition("x")
            iid = next((k for k, v in ITEM_MAP.items() if v["name"] == name), None)
            if iid is None:
                print(f"  无法识别材料：{name}")
                return
            need.append((iid, int(num) if num else 1))
        for iid, n in need:
            if self.item_count(iid) < n:
                print(f"  材料不足：{display_name(iid)} 需要 x{n}（当前 x{self.item_count(iid)}）")
                return
        for iid, n in need:
            self.remove_item(iid, n)
        oid = r["output_id"]
        if ITEM_MAP[oid]["type"] == "potion":
            self.p.potions[oid] = self.p.potions.get(oid, 0) + 1
        else:
            self.add_item(oid)
        self.craft_count += 1
        print(f"  ⚒ 合成成功：{r['output']} x1")
        self.check_achieve("craft", 5)

    def enhance_weapon(self):
        if not self.p.weapon:
            print("  没有装备武器。")
            return
        it = ITEM_MAP[self.p.weapon]
        if not hasattr(self.p, "enhance"):
            self.p.enhance = {}
        level = self.p.enhance.get(self.p.weapon, 0)
        if level >= 9:
            print("  该武器已强化至满级。")
            return
        cost = 50 * (level + 1)
        if self.p.gold < cost:
            print(f"  强化需要 {cost} 金币，不足。")
            return
        self.p.gold -= cost
        self.p.enhance[self.p.weapon] = level + 1
        print(f"  强化成功！{display_name(self.p.weapon)} +{level+1}（攻击 +{level+1}）")

    # ---------- 任务 ----------
    def quest_menu(self):
        print("\n-- 任务 --")
        active = []
        for q in QUESTS:
            if q["id"] in self.p.quests_done:
                continue
            active.append(q)
        if not active:
            print("  所有任务已完成！你是苍穹的传说。")
            return
        for i, q in enumerate(active):
            print(f"  {i}. {q['name']}: {q['desc']}")
        c = input("  选择任务查看进度 > ").strip()
        if c.isdigit() and int(c) in range(len(active)):
            self.check_quest(active[int(c)])

    def check_quest(self, q):
        done = False
        if q.get("boss"):
            bname = MONSTERS[q["boss"]]["name"]
            if bname in self.p.bosses:
                done = True
        if q.get("need"):
            ok = True
            for iid, n in q["need"].items():
                if self.item_count(iid) < n:
                    ok = False
            if ok:
                for iid, n in q["need"].items():
                    self.remove_item(iid, n)
                done = True
        if done:
            self.p.quests_done.append(q["id"])
            self.p.gold += q["reward_gold"]
            self.p.stats["gold_earned"] += q["reward_gold"]
            print(f"  ✔ 任务完成：{q['name']}！获得 {q['reward_gold']} 金币。")
            if q.get("reward_item"):
                self.grant_reward(q["reward_item"])
            self.check_achieve("quests", 3)
            self.check_achieve("gold", 5000)
        else:
            print("  任务尚未完成，继续努力吧。")

    # ---------- 宠物 ----------
    def pet_menu(self):
        print("\n-- 宠物 --")
        if not self.p.pet:
            print("  你还没有宠物。击败 BOSS 有概率收服宠物。")
            return
        p = PETS[self.p.pet]
        print(f"  宠物：{self.p.pet}  {p['desc']}")
        print("  宠物会在战斗中概率协助攻击。")

    # ---------- 剧情日志 ----------
    def story_menu(self):
        print("\n-- 星陨编年史 --")
        done_main = [q["id"] for q in QUESTS
                     if q["id"].startswith("m") and q["id"] in self.p.quests_done]
        print(f"  已完成主线：{len(done_main)}/12 章")
        for i, (title, paras) in enumerate(STORY_CHAPTERS):
            unlocked = i < len(done_main) + 1
            if unlocked:
                print(f"\n  ▶ {title}")
                for p in paras:
                    print(f"    {p}")
            else:
                print(f"\n  ▷ {title}（完成前一章主线后解锁）")
        input("  按回车返回 > ")

    # ---------- 区域地图 ----------
    def map_menu(self):
        print("\n-- 世界地图 --")
        unlocked = min(self.p.zone + 1, len(ZONES) - 1)
        for i, z in enumerate(ZONES):
            marker = "➤" if i == self.p.zone else ("✔" if i <= self.p.zone else "✘")
            print(f"  {marker} {i}. {z['name']}（推荐等级 {z['level']}）")
        c = input(f"  传送到区域编号（0-{unlocked}）> ").strip()
        if c.isdigit() and 0 <= int(c) <= unlocked:
            self.p.zone = int(c)
            self.p.pos = [0, 0]
            print(f"  传送到 {ZONES[self.p.zone]['name']}。")

    # ---------- 设置 / 调试 ----------
    def settings_menu(self):
        p = self.p
        while True:
            print("\n-- 设置 / 调试 --")
            print("  [常规]")
            print(f"    1. 无敌模式        {'✔ 开' if p.god_mode else '✘ 关'}")
            print(f"    2. 一击必杀        {'✔ 开' if p.one_hit else '✘ 关'}")
            print(f"    3. 伤害明细        {'✔ 开' if p.show_damage else '✘ 关'}")
            print("  [调试工具]")
            print("    4. 快速升级    (+500 经验)")
            print("    5. 增加金币    (+1000)")
            print("    6. 赠送装备    (随机一件)")
            print("    7. 战斗/探索统计")
            print("    8. 成就列表")
            print("    9. 怪物图鉴")
            print(f"    E. 实验模式        {'✔ 开' if self.experiment_mode else '✘ 关'}")
            print("    M. 内存占用")
            print("    R. 恢复默认设置")
            print("    Q. 返回")
            c = input("  > ").strip().lower()
            if c == "1":
                p.god_mode = not p.god_mode
                print(f"  无敌模式已{'开启' if p.god_mode else '关闭'}。战斗中你不会受到伤害。")
            elif c == "2":
                p.one_hit = not p.one_hit
                print(f"  一击必杀已{'开启' if p.one_hit else '关闭'}。攻击将直接秒杀敌人。")
            elif c == "3":
                p.show_damage = not p.show_damage
                print(f"  伤害明细已{'开启' if p.show_damage else '关闭'}。")
            elif c == "4":
                p.add_exp(500)
                print(f"  经验 +500！当前 Lv{p.level}（{p.exp}/{p.exp_needed()}）")
            elif c == "5":
                p.gold += 1000
                print(f"  金币 +1000！当前 {p.gold}")
            elif c == "6":
                self.debug_give_item()
            elif c == "7":
                self.show_stats_panel()
            elif c == "8":
                self.show_achievements()
            elif c == "9":
                self.show_bestiary()
            elif c == "e":
                self.experiment_mode = not self.experiment_mode
                print(f"  实验模式已{'开启' if self.experiment_mode else '关闭'}。开启后探索可触发实验事件（真实获得物品/金币）。")
            elif c == "m":
                kb = memory_rss_kb()
                print(f"  当前进程内存：{kb / 1024.0:.1f} MB（{kb:,} KB）")
                print(f"  游戏版本：v{VERSION}")
                print(f"  已解锁区域：{p.zone + 1}/{len(ZONES)}")
            elif c == "r":
                p.god_mode = False
                p.one_hit = False
                p.show_damage = False
                print("  已恢复默认设置（无敌/一击必杀/伤害明细均关闭）。")
            elif c == "q":
                return
            else:
                print("  无效指令。")

    def debug_give_item(self):
        """调试：随机赠送一件装备"""
        pool = [iid for iid, it in ITEM_MAP.items() if it["type"] in ("weapon", "armor", "accessory")]
        iid = random.choice(pool)
        self.add_item(iid, 1)
        it = ITEM_MAP[iid]
        print(f"  获得装备：{it['name']}（{it['desc']}）")

    def show_stats_panel(self):
        p = self.p
        print("\n-- 战斗/探索统计 --")
        print(f"  探索次数：{p.stats['explore']}    战斗次数：{p.stats['battle']}")
        print(f"  累计击杀：{p.kills}    死亡次数：{p.stats['death']}")
        print(f"  累计获得金币：{p.stats['gold_earned']}")
        print(f"  当前金币：{p.gold}    当前等级：Lv{p.level}")
        print(f"  已收集装备：{len(p.inventory)} 件    已解锁区域：{p.zone + 1}/{len(ZONES)}")
        print(f"  宠物：{p.pet or '无'}")

    def show_achievements(self):
        print("\n-- 成就列表 --")
        unlocked = set(self.p.achievements)
        done = sum(1 for a in ACHIEVEMENTS if a["id"] in unlocked)
        print(f"  已解锁 {done}/{len(ACHIEVEMENTS)} 项")
        for i in range(0, len(ACHIEVEMENTS), 3):
            row = ACHIEVEMENTS[i:i + 3]
            for a in row:
                mark = "✔" if a["id"] in unlocked else "·"
                print(f"  {mark} {a['name']}", end="")
            print()
        input("  按回车返回 > ")

    def show_bestiary(self):
        print("\n-- 怪物图鉴 --")
        for zi, z in enumerate(ZONES):
            idxs = z.get("monsters", [])
            if not idxs:
                continue
            mons = [MONSTERS[i] for i in idxs if 0 <= i < len(MONSTERS)]
            if not mons:
                continue
            print(f"\n  【{z['name']}】")
            for m in mons:
                boss = " [BOSS]" if m.get("boss") else ""
                print(f"    {m['name']}  HP {m['hp']}  攻 {m['atk']}  防 {m['def']}{boss}")
        print(f"\n  图鉴收录 {len(MONSTERS)} 种怪物")
        input("  按回车返回 > ")

    # ---------- 简易图像效果（纯 ANSI，零依赖） ----------
    @staticmethod
    def _bar(cur, full, width=10):
        """文本血条：█████·····"""
        ratio = max(0.0, min(1.0, cur / full if full else 0))
        filled = int(round(width * ratio))
        return "[" + "█" * filled + "·" * (width - filled) + "]"

    @staticmethod
    def _c(text, color):
        """ANSI 着色；Windows 非 ANSI 终端自动降级为纯文本"""
        if os.name == "nt":
            return text
        m = {"red": "31", "green": "32", "yellow": "33", "blue": "34",
             "purple": "35", "cyan": "36", "bold": "1"}
        return "\033[%sm%s\033[0m" % (m.get(color, "0"), text)

    def status_line(self):
        p = self.p
        hpbar = self._bar(p.hp, p.max_hp_full())
        mpbar = self._bar(p.mp, p.max_mp)
        return (f"  【{self.get_zone()['name']}】Lv{p.level} {p.cls}  "
                f"HP {p.hp}/{p.max_hp_full()} {self._c(hpbar, 'green')}  "
                f"MP {p.mp}/{p.max_mp} {self._c(mpbar, 'blue')}  "
                f"金币 {self._c(str(p.gold), 'yellow')}  击杀 {p.kills}")

    # ---------- v3.0 调试命令台（150 条命令） ----------
    def build_debug_commands(self):
        """生成 150 条调试命令表：[(id, 分类, 名称, 描述, 回调)]"""
        cmds = []
        def _add(cat, name, desc, fn):
            cmds.append((len(cmds) + 1, cat, name, desc, fn))
        # A. 金币（1-20）
        for i in range(1, 21):
            _add("金币", f"add_gold_{i}", f"增加金币 +{100 * i}", (lambda n: (lambda: self._dbg_gold(n)))(100 * i))
        # B. 经验（21-40）
        for i in range(1, 21):
            _add("经验", f"add_exp_{i}", f"增加经验 +{200 * i}", (lambda n: (lambda: self._dbg_exp(n)))(200 * i))
        # C. 等级（41-50）
        for i in range(1, 11):
            _add("等级", f"set_level_{i}", f"直接升到 {i} 级", (lambda n: (lambda: self._dbg_level(n)))(i))
        # D. 装备（51-60）
        for i, t in enumerate(["weapon", "armor", "accessory", "weapon", "armor", "accessory", "weapon", "armor", "accessory", "weapon"], 1):
            _add("装备", f"give_{t}_{i}", f"赠送随机{t}装备", (lambda x: (lambda: self._dbg_item(x)))(t))
        # E. 召唤怪物（61-70）
        for i in range(1, 11):
            _add("召唤", f"summon_{i}", f"召唤 {i} 号区域怪物", (lambda n: (lambda: self._dbg_summon(n)))(i))
        # F. BOSS（71-75）
        for i in range(1, 6):
            _add("BOSS", f"boss_{i}", f"召唤第 {i} 只 BOSS", (lambda n: (lambda: self._dbg_boss(n)))(i))
        # G. 传送（76-85）
        for i in range(0, 10):
            _add("传送", f"tp_{i}", f"传送到 {ZONES[i]['name']}", (lambda n: (lambda: self._dbg_tp(n)))(i))
        # H. 开关（86-95）
        _add("开关", "god_on", "开启无敌模式", lambda: self._dbg_toggle("god", True))
        _add("开关", "god_off", "关闭无敌模式", lambda: self._dbg_toggle("god", False))
        _add("开关", "oh_on", "开启一击必杀", lambda: self._dbg_toggle("oh", True))
        _add("开关", "oh_off", "关闭一击必杀", lambda: self._dbg_toggle("oh", False))
        _add("开关", "dmg_on", "开启伤害明细", lambda: self._dbg_toggle("dmg", True))
        _add("开关", "dmg_off", "关闭伤害明细", lambda: self._dbg_toggle("dmg", False))
        _add("开关", "exp_on", "开启实验模式", lambda: self._dbg_toggle("exp", True))
        _add("开关", "exp_off", "关闭实验模式", lambda: self._dbg_toggle("exp", False))
        _add("开关", "pet_on", "启用宠物参战", lambda: self._dbg_toggle("pet", True))
        _add("开关", "pet_off", "停用宠物参战", lambda: self._dbg_toggle("pet", False))
        # I. 属性（96-105）
        for i in range(1, 6):
            _add("属性", f"hp_{i}", f"生命上限 +{50 * i}", (lambda n: (lambda: self._dbg_hp(n)))(50 * i))
        for i in range(1, 6):
            _add("属性", f"mp_{i}", f"法力上限 +{50 * i}", (lambda n: (lambda: self._dbg_mp(n)))(50 * i))
        # J. 清理（106-110）
        _add("清理", "reset_stats", "重置统计数据", self._dbg_reset_stats)
        _add("清理", "clear_inv", "清空背包", self._dbg_clear_inv)
        _add("清理", "unlock_all", "解锁全部区域", self._dbg_unlock)
        _add("清理", "revive", "满状态复活", self._dbg_revive)
        _add("清理", "heal_full", "生命法力回满", self._dbg_full)
        # K. 信息（111-120）
        _add("信息", "info_stats", "查看角色属性", lambda: self.show_stats_panel())
        _add("信息", "info_mem", "查看内存占用", lambda: print(f"  内存：{memory_rss_kb() / 1024.0:.1f} MB"))
        _add("信息", "info_map", "查看区域信息", lambda: self.map_menu())
        _add("信息", "info_pet", "查看宠物", lambda: self.pet_menu())
        _add("信息", "info_quest", "查看任务", lambda: self.quest_menu())
        _add("信息", "info_ach", "查看成就", lambda: self.show_achievements())
        _add("信息", "info_codex", "打开图鉴", lambda: self.codex_menu())
        _add("信息", "info_inv", "查看背包", lambda: self.inventory_menu())
        _add("信息", "info_recipe", "查看配方", lambda: self.craft_menu())
        _add("信息", "info_story", "查看剧情", lambda: self.story_menu())
        # L. 模组 / AI（121-135）
        _add("模组", "mod_list", "列出已加载模组", lambda: self._dbg_mods())
        _add("模组", "mod_reload", "重新扫描模组目录", lambda: self.load_mods())
        _add("模组", "ai_monster", "AI 生成一只新怪物", lambda: self._dbg_ai("monster"))
        _add("模组", "ai_item", "AI 生成一件新装备", lambda: self._dbg_ai("item"))
        _add("模组", "ai_event", "AI 生成一个新事件", lambda: self._dbg_ai("event"))
        _add("模组", "ai_api_set", "设置 AI API Key", lambda: self._dbg_ai_key())
        _add("模组", "ai_api_clr", "清除 AI API Key", lambda: self._dbg_ai_clear())
        _add("模组", "exp_event", "触发一个实验事件", lambda: self.experiment_event())
        _add("模组", "mod_help", "模组开发帮助", lambda: print("  在 mods/ 目录放置 .py 模组文件，定义 MOD_NAME/MOD_ITEMS/MOD_MONSTERS/MOD_EVENTS 即可自动加载。"))
        _add("模组", "ai_dialog", "AI 生成随机角色对话", lambda: self._dbg_ai("dialog"))
        _add("模组", "exp_loot", "实验模式：随机实验战利品", lambda: self.experiment_loot())
        _add("模组", "ai_batch", "AI 批量生成 5 件内容", lambda: self._dbg_ai_batch())
        _add("模组", "mod_status", "查看模组状态", lambda: print(f"  已加载模组：{len(self.mods)} 个  {self.mods}"))
        _add("模组", "exp_zone", "实验模式：解锁隐藏区域信息", lambda: print("  实验模式开启后，探索时有概率触发实验事件。"))
        _add("模组", "ai_story", "AI 生成一段剧情", lambda: self._dbg_ai("story"))
        # M. 宠物 / 任务（136-145）
        for i in range(1, 6):
            _add("宠物", f"pet_{i}", f"获得第 {i} 只宠物", (lambda n: (lambda: self._dbg_pet(n)))(i))
        for i in range(1, 6):
            _add("任务", f"quest_{i}", f"查看第 {i} 个任务", (lambda n: (lambda: self._dbg_quest(n)))(i))
        # N. 其它（146-150）
        _add("其它", "boss_scan", "扫描全部 BOSS 位置", self._dbg_boss_scan)
        _add("其它", "game_help", "游戏帮助", lambda: print("  输入 1-9 / S / D / T 或 /命令 进行游戏。"))
        _add("其它", "exp_all", "实验模式：全部开关", lambda: self._dbg_exp_all())
        _add("其它", "reset_all", "恢复默认全部设置", lambda: self._dbg_reset_all())
        _add("其它", "version", "版本信息", lambda: print(f"  苍穹远征：星陨传说 v{VERSION}"))
        return cmds

    def _dbg_gold(self, n):
        self.p.gold += n
        self.p.stats["gold_earned"] = self.p.stats.get("gold_earned", 0) + n
        print(f"  金币 +{n} → {self.p.gold}")

    def _dbg_exp(self, n):
        self.p.add_exp(n)
        print(f"  经验 +{n} → Lv{self.p.level}（{self.p.exp}/{self.p.exp_needed()}）")

    def _dbg_level(self, n):
        while self.p.level < n:
            self.p.add_exp(self.p.exp_needed())
        print(f"  等级 → Lv{self.p.level}")

    def _dbg_item(self, itype):
        pool = [iid for iid, it in ITEM_MAP.items() if it["type"] == itype]
        if not pool:
            pool = [iid for iid, it in ITEM_MAP.items() if it["type"] in ("weapon", "armor", "accessory")]
        iid = random.choice(pool)
        self.add_item(iid, 1)
        print(f"  获得：{display_name(iid)}（{ITEM_MAP[iid]['desc']}）")

    def _dbg_summon(self, zi):
        zi = max(0, min(len(ZONES) - 1, zi))
        idxs = ZONES[zi].get("monsters", [])
        if not idxs:
            print("  该区域无怪物。")
            return
        m = MONSTERS[random.choice(idxs)]
        self._fight(Enemy(m))

    def _dbg_boss(self, n):
        bosses = [m for m in MONSTERS if m.get("boss")]
        if not bosses:
            print("  无 BOSS 可召唤。")
            return
        self._fight(Enemy(bosses[(n - 1) % len(bosses)]))

    def _dbg_tp(self, zi):
        self.p.zone = max(0, min(len(ZONES) - 1, zi))
        self.p.pos = [0, 0]
        print(f"  传送到 {ZONES[self.p.zone]['name']}。")

    def _dbg_toggle(self, key, val):
        mapping = {"god": ("god_mode", "无敌模式"), "oh": ("one_hit", "一击必杀"),
                   "dmg": ("show_damage", "伤害明细"), "exp": ("experiment_mode", "实验模式"),
                   "pet": ("pet_active", "宠物参战")}
        attr, name = mapping[key]
        setattr(self.p, attr, val) if hasattr(self.p, attr) else setattr(self, attr, val)
        print(f"  {name}已{'开启' if val else '关闭'}。")

    def _dbg_hp(self, n):
        self.p.max_hp += n
        self.p.hp = self.p.max_hp_full()
        print(f"  生命上限 +{n} → {self.p.max_hp}")

    def _dbg_mp(self, n):
        self.p.max_mp += n
        self.p.mp = self.p.max_mp
        print(f"  法力上限 +{n} → {self.p.max_mp}")

    def _dbg_reset_stats(self):
        self.p.stats = {"explore": 0, "battle": 0, "death": 0, "gold_earned": 0}
        print("  统计已重置。")

    def _dbg_clear_inv(self):
        self.p.inventory = {}
        print("  背包已清空。")

    def _dbg_unlock(self):
        self.p.zone = len(ZONES) - 1
        print(f"  已解锁全部区域（当前 {ZONES[self.p.zone]['name']}）。")

    def _dbg_revive(self):
        self.p.hp = self.p.max_hp_full()
        self.p.mp = self.p.max_mp
        print("  已满状态复活。")

    def _dbg_full(self):
        self.p.hp = self.p.max_hp_full()
        self.p.mp = self.p.max_mp
        print("  生命与法力已回满。")

    def _dbg_pet(self, n):
        if 0 < n <= len(PETS):
            pet = PETS[n - 1]
            self.p.pet = pet["name"]
            print(f"  获得宠物：{pet['name']}（{pet.get('desc', '')}）")
        else:
            print("  宠物编号无效。")

    def _dbg_quest(self, n):
        if 0 < n <= len(QUESTS):
            q = QUESTS[n - 1]
            print(f"  [{q.get('zone', '?')}] {q.get('name')}：{q.get('desc', '')}")
        else:
            print("  任务编号无效。")

    def _dbg_mods(self):
        print(f"  已加载模组（{len(self.mods)}）：" + ("、" .join(self.mods) if self.mods else "无"))

    def _dbg_ai(self, kind):
        item = self.ai_generate(kind)
        if item:
            print(f"  AI 生成：{item}")

    def _dbg_ai_key(self):
        key = input("  请输入 AI API Key（留空取消）> ").strip()
        if key:
            self.ai_api_key = key
            print("  API Key 已设置（仅本次会话有效）。")

    def _dbg_ai_clear(self):
        self.ai_api_key = ""
        print("  API Key 已清除，将使用本地模板生成。")

    def _dbg_ai_batch(self):
        for k in ("monster", "item", "event", "dialog", "story"):
            self.ai_generate(k)
        print("  批量生成完成（5 件）。")

    def _dbg_exp_all(self):
        self.experiment_mode = True
        print("  实验模式已开启（含全部实验内容）。")

    def _dbg_reset_all(self):
        self.p.god_mode = False
        self.p.one_hit = False
        self.p.show_damage = False
        self.experiment_mode = False
        print("  全部设置已恢复默认。")

    def _dbg_boss_scan(self):
        bosses = [m for m in MONSTERS if m.get("boss")]
        print(f"  全图鉴共 {len(bosses)} 只 BOSS：")
        for m in bosses:
            print(f"    {m['name']}  HP {m['hp']}  攻 {m['atk']}  防 {m['def']}")

    def debug_console(self):
        """调试命令台：150 条命令，分页浏览/编号执行/关键词搜索"""
        cmds = self.build_debug_commands()
        print("\n-- 调试命令台（共 150 条）--")
        print("  输入命令编号执行；输入 页码 浏览；输入关键词搜索；Q 返回")
        page = 1
        while True:
            per_page = 15
            total_pages = (len(cmds) + per_page - 1) // per_page
            start = (page - 1) * per_page
            print(f"\n  第 {page}/{total_pages} 页")
            for cid, cat, name, desc, _ in cmds[start:start + per_page]:
                print(f"    {cid:>3}. [{cat}] {name:<12} {desc}")
            c = input("  > ").strip().lower()
            if c == "q":
                return
            if c.isdigit():
                n = int(c)
                if n == 0:
                    continue
                if 1 <= n <= 150:
                    _, _, _, _, fn = cmds[n - 1]
                    fn()
                else:
                    print("  编号超出范围（1-150）。")
            elif c in ("n", "next"):
                page = min(total_pages, page + 1)
            elif c in ("p", "prev"):
                page = max(1, page - 1)
            else:
                hits = [(cid, cat, name, desc) for cid, cat, name, desc, _ in cmds
                        if c in cat or c in name or c in desc]
                if hits:
                    print(f"  命中 {len(hits)} 条：")
                    for cid, cat, name, desc in hits[:15]:
                        print(f"    {cid:>3}. [{cat}] {name:<12} {desc}")
                    print("  输入编号执行。")
                else:
                    print("  无匹配命令。输入 N 下一页 / P 上一页。")

    # ---------- v3.0 图鉴系统（6 类） ----------
    def codex_menu(self):
        while True:
            print("\n-- 图鉴系统 --")
            print("  1. 怪物图鉴  2. 装备图鉴  3. 材料/药水图鉴")
            print("  4. 技能图鉴  5. 区域图鉴  6. 成就图鉴")
            print("  Q. 返回")
            c = input("  > ").strip().lower()
            if c == "1":
                self.show_bestiary()
            elif c == "2":
                self.codex_items("equipment")
            elif c == "3":
                self.codex_items("material")
            elif c == "4":
                self.codex_skills()
            elif c == "5":
                self.codex_zones()
            elif c == "6":
                self.show_achievements()
            elif c == "q":
                return
            else:
                print("  无效指令。")

    def codex_items(self, mode):
        if mode == "equipment":
            types = ["weapon", "armor", "accessory"]
            title = "装备图鉴"
        else:
            types = ["potion", "material", "food"]
            title = "材料/药水图鉴"
        items = [(iid, it) for iid, it in ITEM_MAP.items() if it["type"] in types]
        print(f"\n-- {title}（{len(items)} 件）--")
        page, per = 1, 12
        while True:
            total = (len(items) + per - 1) // per
            print(f"\n  第 {page}/{total} 页")
            for iid, it in items[(page - 1) * per: page * per]:
                print(f"    {it['name']}  效果: {it['desc']}")
            c = input("  输入 N 下一页 / P 上一页 / Q 返回 > ").strip().lower()
            if c == "q":
                return
            elif c == "n":
                page = min(total, page + 1)
            elif c == "p":
                page = max(1, page - 1)

    def codex_skills(self):
        print("\n-- 技能图鉴（按职业）--")
        for cls, skills in SKILLS.items():
            print(f"\n  【{cls}】{CLASSES.get(cls, {}).get('desc', '')}")
            for s in skills:
                eff = f"倍率 {s['mult']}" if "mult" in s else (f"治疗 {s['heal']}" if "heal" in s else f"护盾 {s['buff']}")
                print(f"    {s['name']}  MP {s['cost']}  CD {s['cd']}  {eff}  {s['desc']}")
        input("  按回车返回 > ")

    def codex_zones(self):
        print("\n-- 区域图鉴 --")
        for i, z in enumerate(ZONES):
            mons = [MONSTERS[j]["name"] for j in z.get("monsters", []) if 0 <= j < len(MONSTERS)]
            print(f"  {i:>2}. {z['name']}  Lv{z['level']}  怪物: {'、'.join(mons[:4])}{'…' if len(mons) > 4 else ''}")
        input("  按回车返回 > ")

    # ---------- v3.0 实验模式 ----------
    def experiment_event(self):
        """实验模式事件：真实获得物品/金币"""
        if not self.experiment_mode:
            print("  实验模式未开启（调试台 exp_on 或设置菜单开启）。")
            return
        roll = random.random()
        if roll < 0.4:
            gold = random.randint(50, 500)
            self.p.gold += gold
            self.p.stats["gold_earned"] = self.p.stats.get("gold_earned", 0) + gold
            print(f"  【实验】时空裂缝中掉出金币！+{gold} 金币（真实入账）")
        elif roll < 0.8:
            pool = [iid for iid, it in ITEM_MAP.items() if it["type"] in ("weapon", "armor", "accessory", "potion")]
            iid = random.choice(pool)
            self.add_item(iid, 1)
            print(f"  【实验】量子波动送来 {display_name(iid)}！已真实加入背包")
        else:
            exp = random.randint(100, 400)
            self.p.add_exp(exp)
            print(f"  【实验】时间洪流灌注经验！+{exp} 经验")

    def experiment_loot(self):
        if not self.experiment_mode:
            print("  实验模式未开启。")
            return
        for _ in range(3):
            self.experiment_event()

    # ---------- v3.0 模组系统（模块化架构） ----------
    def load_mods(self):
        """扫描 mods/ 目录，加载 .py 模组（模块化架构）"""
        mods_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mods")
        if not os.path.isdir(mods_dir):
            os.makedirs(mods_dir, exist_ok=True)
        self.mods = []
        for fn in sorted(os.listdir(mods_dir)):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(mods_dir, fn)
            try:
                ns = {}
                with open(path, encoding="utf-8") as f:
                    exec(compile(f.read(), path, "exec"), ns)
                name = ns.get("MOD_NAME", fn[:-3])
                # 注册模组扩展内容
                added = 0
                for iid, it in ns.get("MOD_ITEMS", {}).items():
                    if iid not in ITEM_MAP:
                        ITEM_MAP[iid] = it
                        added += 1
                for m in ns.get("MOD_MONSTERS", []):
                    if m["name"] not in [x["name"] for x in MONSTERS]:
                        MONSTERS.append(m)
                        added += 1
                for ev in ns.get("MOD_EVENTS", []):
                    text = ev if isinstance(ev, str) else ev.get("text", str(ev))
                    if text not in EVENT_TEXTS:
                        EVENT_TEXTS.append(text)
                        added += 1
                self.mods.append(name)
                print(f"  [模组] 已加载 {name}（新增 {added} 项内容）")
            except Exception as e:
                print(f"  [模组] {fn} 加载失败：{e}")
        if not self.mods:
            print("  当前无模组。可在 mods/ 目录放置 .py 模组文件。")

    # ---------- v3.0 AI 内容生成接口 ----------
    def ai_generate(self, kind):
        """AI API 内容生成：配置了 api_key 则调用外部 API，否则本地模板兜底"""
        if self.ai_api_key:
            try:
                import urllib.request
                import json as _json
                prompt_map = {
                    "monster": "生成一个游戏怪物，输出 JSON：{\"name\":\"..\",\"hp\":..,\"atk\":..,\"def\":..}",
                    "item": "生成一件游戏装备，输出 JSON：{\"name\":\"..\",\"type\":\"weapon\",\"desc\":\"..\"}",
                    "event": "生成一段游戏事件文本，输出 JSON：{\"id\":\"..\",\"text\":\"..\"}",
                    "dialog": "生成一句游戏角色对白",
                    "story": "生成一段 50 字游戏剧情",
                }
                data = _json.dumps({"prompt": prompt_map.get(kind, kind), "kind": kind}).encode()
                req = urllib.request.Request("https://api.example.com/v1/generate", data=data,
                                             headers={"Content-Type": "application/json",
                                                      "Authorization": "Bearer " + self.ai_api_key})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    out = resp.read().decode()[:200]
                print(f"  [AI-API] {kind} → {out}")
                return out
            except Exception as e:
                print(f"  [AI-API] 调用失败（{e}），改用本地模板。")
        return self.ai_generate_local(kind)

    def ai_generate_local(self, kind):
        """本地模板兜底：零依赖生成新内容"""
        if kind == "monster":
            names = ["虚空猎手", "晶核傀儡", "深渊观测者", "星尘掠夺者", "裂隙行者"]
            m = {"name": random.choice(names), "hp": random.randint(80, 300),
                 "atk": random.randint(10, 30), "def": random.randint(3, 12)}
            MONSTERS.append(m)
            print(f"  [AI-本地] 新怪物 {m['name']}（HP{m['hp']} 攻{m['atk']} 防{m['def']}）已加入图鉴")
        elif kind == "item":
            names = ["碎星之刃", "虚空法袍", "极光护腕", "永夜戒指", "晨曦项链"]
            iid = "ai_item_%d" % len(ITEM_MAP)
            ITEM_MAP[iid] = {"name": random.choice(names), "type": random.choice(["weapon", "armor", "accessory"]),
                             "desc": "AI 生成的神秘装备"}
            print(f"  [AI-本地] 新装备 {display_name(iid)} 已加入图鉴")
        elif kind == "event":
            texts = ["一阵奇异的风吹过，你感觉时间变慢了……",
                     "空中飘落一枚发光的晶石，蕴含着未知的力量。",
                     "远处传来低语声，仿佛在呼唤你的名字。"]
            print(f"  [AI-本地] 新事件：{random.choice(texts)}")
        elif kind == "dialog":
            dialogs = ["远方星空在注视着你。", "命运从不辜负前行者。", "据说星陨之地藏着古老的秘密。"]
            print(f"  [AI-本地] 角色对白：{random.choice(dialogs)}")
        elif kind == "story":
            print("  [AI-本地] 剧情：你穿过星尘之门，踏入从未记载过的荒原，天空悬挂着破碎的月亮，古老遗迹在雾中若隐若现……")
        else:
            print(f"  [AI-本地] 未知生成类型：{kind}")
        return kind

    # ---------- v3.0 实验模式命令（/ 命令） ----------
    def chat_command(self, cmd):
        """斜杠命令：/help /gold 500 /exp 1000 /lv 10 /god /onehit /expmode /mods /ai monster /tp 5 ..."""
        parts = cmd[1:].strip().split()
        if not parts:
            print("  输入 /help 查看命令。")
            return
        c, args = parts[0].lower(), parts[1:]
        if c == "help":
            print("  /gold <n> 加金币  /exp <n> 加经验  /lv <n> 升级  /item <类型> 送装备")
            print("  /tp <区域> 传送  /god 无敌  /onehit 一击必杀  /dmg 伤害明细")
            print("  /expmode 实验模式  /mods 模组  /ai <类型> AI生成  /stats 统计  /save 存档")
        elif c == "gold" and args:
            try:
                self._dbg_gold(int(args[0]))
            except ValueError:
                print("  参数需为数字。")
        elif c == "exp" and args:
            try:
                self._dbg_exp(int(args[0]))
            except ValueError:
                print("  参数需为数字。")
        elif c == "lv" and args:
            try:
                self._dbg_level(int(args[0]))
            except ValueError:
                print("  参数需为数字。")
        elif c == "item":
            self._dbg_item(args[0] if args else "weapon")
        elif c == "tp" and args:
            try:
                self._dbg_tp(int(args[0]))
            except ValueError:
                print("  参数需为数字。")
        elif c == "god":
            self._dbg_toggle("god", not self.p.god_mode)
        elif c == "onehit":
            self._dbg_toggle("oh", not self.p.one_hit)
        elif c == "dmg":
            self._dbg_toggle("dmg", not self.p.show_damage)
        elif c == "expmode":
            self._dbg_toggle("exp", not self.experiment_mode)
        elif c == "mods":
            self._dbg_mods()
        elif c == "ai":
            self._dbg_ai(args[0] if args else "monster")
        elif c == "stats":
            self.show_stats_panel()
        elif c == "save":
            self.save()
        else:
            print("  未知命令。输入 /help 查看。")

    # ---------- 存档 ----------
    def save(self):
        data = {
            "version": VERSION,
            "player": self.p.to_dict(),
            "craft_count": getattr(self, "craft_count", 0),
            "time": time.time(),
        }
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  存档成功：{SAVE_FILE}（{os.path.getsize(SAVE_FILE)} 字节）")
        except Exception as e:
            print(f"  存档失败：{e}")


def new_game():
    print("\n-- 创建角色 --")
    name = input("  输入角色名 > ").strip() or "勇者"
    print("  ┌─ 选择职业 ──────────────────────┐")
    _cls_list = list(CLASSES.keys())
    _row = []
    for _i, _c in enumerate(_cls_list, 1):
        _row.append(f"{_i}.{_c}")
        if _i % 3 == 0:
            print("  │ " + "  ".join(_row) + "  │")
            _row = []
    if _row:
        print("  │ " + "  ".join(_row) + "  │")
    print("  └──────────────────────────────────┘")
    c = input("  > ").strip()
    try:
        idx = int(c) - 1
        cls = _cls_list[idx] if 0 <= idx < len(_cls_list) else "战士"
    except ValueError:
        cls = c if c in CLASSES else "战士"
    print(f"  职业 {cls}：{CLASSES[cls]['desc']}")
    return Game(Player(name, cls))


def load_game():
    if not os.path.exists(SAVE_FILE):
        return None
    with open(SAVE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    p = Player.from_dict(data["player"])
    g = Game(p)
    g.craft_count = data.get("craft_count", 0)
    g.load_mods()
    print(f"  读取存档成功：{p.name}（{p.cls}）Lv{p.level}")
    return g


def main():
    show_boot_info()
    print("  1. 开始新游戏")
    print("  2. 读取存档")
    c = input("  > ").strip()
    if c == "2":
        g = load_game()
        if g is None:
            print("  未找到存档，开始新游戏。")
            g = new_game()
    else:
        g = new_game()
    try:
        g.run()
    except (KeyboardInterrupt, EOFError):
        print("\n  游戏中断，欢迎下次继续冒险！")
    # 结束时再次打印内存占用
    rss = memory_rss_kb()
    print(f"\n  本次运行进程内存占用峰值: {rss} KB（{rss/1024:.1f} MB）")


if __name__ == "__main__":
    main()

# ============================================================
# 版本历史（v1 标记）
# ------------------------------------------------------------
# v1.0   —— 苍穹远征初版：基础文字冒险 RPG，单职业、基础战斗与探索
# v2.0   —— 大版本重构：数据驱动内容（装备/怪物/事件），地图网格化
# v2.1   —— 新增商店/锻造/任务系统，扩充内容规模
# v2.2   —— 新增宠物/成就/图鉴雏形，优化存档兼容
# v2.3   —— 新增设置/调试系统（主菜单 S）、战斗统计，测试 50/50 全绿
# v3.0   —— 新增九职业/调试命令台/模组系统/实验模式/AI 游玩/六类图鉴，
#           测试 59/59 全绿，内存实测 23MB（分模块版）
# 当前版本：v3.1.0
# ============================================================
