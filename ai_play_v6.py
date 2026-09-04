# -*- coding: utf-8 -*-
"""
《苍穹远征：星陨传说》V6 AI 自动游玩引擎
========================================
解决旧版 AI「只会卡在第一大关刷怪」问题，采用：
  - 策略规则库 ai_rules_v5.py（职业 x 等级段 x 局势 决策矩阵）驱动行为加权
  - 阶段状态机：练级 -> 购装 -> 区域 BOSS 攻坚 -> 推进区域 -> DLC 勇者之路 -> 终局清剿
  - 支持自定义插件（plugins/*.py 钩子）、API 决策接入（--api-url）、MCP 服务（--mcp-port）
  - 全程防御性策略：血量门槛、死亡避让、药水自动补给、按阶段自动存档
纯标准库，零第三方依赖。
"""
import argparse
import json
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import celestial_expedition_v6 as ce
except ImportError:
    import celestial_expedition as ce

try:
    import ai_rules_v6 as RULES
except ImportError:
    RULES = None

DEFAULT_PLUGIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")


# ---------------------------------------------------------------------------
# 插件系统：plugins/*.py 可定义以下钩子，全部可选：
#   on_start(ai)           启动后调用
#   on_round(ai, rnd)      每回合开始
#   on_decision(ai, rnd, candidates)  决策前可改候选动作权重
#   on_battle_result(ai, ok, enemy)   每次战斗结束后
#   on_boss_kill(ai, spec) 击败 BOSS 后
#   on_save(ai)            每次存档后
# ---------------------------------------------------------------------------
def load_plugins(plugin_dir):
    found = []
    if not os.path.isdir(plugin_dir):
        return found
    for fn in sorted(os.listdir(plugin_dir)):
        if not fn.endswith(".py") or fn.startswith("_"):
            continue
        path = os.path.join(plugin_dir, fn)
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("ai_plugin_" + fn[:-3], path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            hooks = {}
            for h in ("on_start", "on_round", "on_decision", "on_battle_result",
                      "on_boss_kill", "on_save"):
                if hasattr(mod, h):
                    hooks[h] = getattr(mod, h)
            if hooks:
                found.append((fn, hooks))
                print(f"  [AI插件] 已加载 {fn}: {list(hooks.keys())}")
        except Exception as e:
            print(f"  [AI插件] {fn} 加载失败: {e}")
    return found


def fire(plugins, hook, *args, **kwargs):
    for _fn, hooks in plugins:
        if hook in hooks:
            try:
                hooks[hook](*args, **kwargs)
            except Exception as e:
                print(f"  [AI插件] 钩子 {hook} 异常: {e}")


class AIPlayer:
    """V6 AI 控制器：规则驱动 + 状态机 + 可插拔扩展；支持 --fast 高速引擎与 --bench 战斗基准"""

    # 动作 -> 实现方法名
    ACTIONS = {
        "upgrade": "do_upgrade", "buy": "do_buy", "boss": "do_boss",
        "advance": "do_advance", "rest": "do_rest", "craft": "do_craft",
        "explore": "do_explore", "task": "do_task",
    }

    def __init__(self, game, rounds=5000, save_name="starfall_save_v6.json",
                 quiet=False, plugins=None, api_url=None, api_key="",
                 mcp_port=0, aggressive=False, long_run=False, max_sec=0,
                 fast=False):
        self.g = game
        self.rounds = rounds
        self.save_name = save_name
        self.quiet = quiet
        self.long_run = long_run
        self.max_sec = max_sec
        self.api_url = api_url
        self.api_key = api_key
        self.aggressive = aggressive
        self.logs = []
        self.plugins = plugins or []
        self.round = 0
        self.stuck_counter = 0          # 连续无进展计数（防卡死）
        self.last_level = game.p.level
        self.last_zone = game.p.zone
        self.last_bosses = len(game.p.bosses)
        self.total_battles = 0
        self.total_boss_wins = 0
        self.total_deaths = 0
        self.potion_bought = 0
        self.gear_bought = 0
        self.zone_advanced = 0
        self._state = "init"
        self._zone_blacklist = set()    # AI 判断暂无法挑战的区域
        self._mcp = None
        self._decision_log = []
        self.health_calls = 0
        self.fast = fast          # V6 高速引擎：轻决策 + 快速战斗 + 稀疏维护
        self._grind_zi = -1
        self._grind_pool = []

    # ---------------- 基础工具 ----------------
    def log(self, text):
        if self.fast:
            return
        if not self.quiet:
            print(text)
        self.logs.append(text)
        if self.long_run and len(self.logs) > 2000:
            self.logs = self.logs[-1000:]

    def cls(self):
        return self.g.p.cls

    def segment(self):
        return min(20, max(1, (self.g.p.level - 1) // 10 + 1))

    def rules_weights(self):
        """从决策矩阵取当前权重，应用局势覆盖"""
        w = dict(RULES.MATRIX.get(self.cls(), RULES.MATRIX.get("战士", {}))
                 .get(self.segment(), {})) if RULES else None
        if not w:
            w = {"upgrade": 8, "buy": 6, "boss": 6, "advance": 5,
                 "rest": 5, "craft": 3, "explore": 3, "task": 3}
        p = self.g.p
        hp_ratio = p.hp / max(1, p.max_hp_full())
        if hp_ratio < 0.40:
            w = dict(RULES.DANGER_OVERRIDE)
            self.health_calls += 1
        elif self.aggressive and hp_ratio >= 0.7:
            w["boss"] = w.get("boss", 5) + 3
        if p.gold > p.level * 180:
            for k, dv in (RULES.RICH_OVERRIDE if RULES else {}).items():
                w[k] = w.get(k, 5) + dv
                if w[k] < 0:
                    w[k] = 0
        if p.level >= 180:
            for k, dv in (RULES.ENDGAME_BIAS if RULES else {}).items():
                w[k] = w.get(k, 5) + dv
        return {k: max(0, v) for k, v in w.items()}

    def choose_action(self):
        """加权随机选动作；卡住时强制换动作防死循环"""
        w = self.rules_weights()
        fire(self.plugins, "on_decision", self, self.round, w)
        if self.stuck_counter >= 6:
            # 防卡死：强制做一些有变化的事
            for forced in ("advance", "boss", "buy", "explore"):
                if forced in w:
                    w[forced] = w.get(forced, 0) + 40
            self.stuck_counter = 0
        acts = list(w.keys())
        weights = [w[a] for a in acts]
        return random.choices(acts, weights=weights, k=1)[0]

    def fast_action(self):
        """V6 高速引擎轻决策：不做规则矩阵与插件广播，直接按状态机取动作"""
        p = self.g.p
        r = self.round
        if self.stuck_counter >= 6:
            self.stuck_counter = 0
            return "advance"
        if p.hp < p.max_hp_full() * 0.60:
            return "rest"
        # V6.1 boss 攻坚放宽：等级接近区域即挑战，打不过会安全跳过练级再战
        if r % 19 == 0 and p.hp >= p.max_hp_full() * 0.88 and p.level >= self.g.get_zone().get("level", 0) - 2:
            return "boss"
        if r % 41 == 0:
            return "advance"
        return "upgrade"

    def zone_pool(self, zi=None):
        zi = self.g.p.zone if zi is None else zi
        zone = ce.ZONES[zi]
        return [ce.MONSTERS[i] for i in zone.get("monsters", [])]

    def zone_boss_specs(self, zi=None):
        return [m for m in self.zone_pool(zi) if m.get("boss")]

    def zone_best_exp(self, zi=None):
        pool = self.zone_pool(zi)
        return max((m.get("exp", 0), m) for m in pool)[1] if pool else None

    def safe_zone_targets(self):
        """可安全前往的区域：level 门槛内 且 池非空"""
        p = self.g.p
        for zi in range(len(ce.ZONES)):
            z = ce.ZONES[zi]
            pool = z.get("monsters", [])
            if not pool:
                continue
            if zi in self._zone_blacklist:
                continue
            if z.get("level", 0) <= p.level + 12:
                yield zi, z, pool
    # ---- 血线与战斗安全 ----
    def auto_use_potion(self, ratio=0.6):
        p = self.g.p
        for iid, n in list(p.potions.items()):
            if n <= 0:
                continue
            it = ce.ITEM_MAP.get(iid) or {}
            if True:  # potions 字典内容均视为治疗药水
                if p.hp < p.max_hp_full() * ratio:
                    p.potions[iid] -= 1
                    heal = it.get("heal", p.max_hp_full() // 4)
                    p.hp = min(p.max_hp_full(), p.hp + heal)
                    return True
        return False

    def buy_potion(self):
        """自动补货：买最划算治疗药水并存入 potions"""
        p = self.g.p
        best, best_id = None, None
        for iid, it in ce.ITEM_MAP.items():
            if it.get("type") == "potion" and it.get("heal"):
                eff = it["heal"] / max(1, it.get("price", 1))
                if best is None or eff > best:
                    best = eff
                    best_id = iid
        if not best_id:
            return False
        price = ce.ITEM_MAP[best_id].get("price", 50)
        if p.gold >= price:
            p.gold -= price
            p.potions[best_id] = p.potions.get(best_id, 0) + 1
            self.potion_bought += 1
            return True
        return False

    # 保底：gold 若低于阈值则战斗攒钱
    def ensure_gold_floor(self):
        p = self.g.p
        return p.gold >= max(200, p.level * 20)

    def _fight_safe(self, enemy):
        """调用自动战斗并统计，返回胜负"""
        p = self.g.p
        # V6.1 安全评估（AI 不送死）：低血硬仗 / 打不动 / 承伤扛不住 → None（稍后再战）
        if p.hp < p.max_hp_full() * 0.45 and enemy.get("hp", 0) > p.hp * 1.2:
            return None
        if enemy.get("def", 0) > p.atk() * 1.5:
            return None
        if enemy.get("atk", 0) > max(p.defense() * 1.5, 1) and enemy.get("hp", 0) > p.max_hp_full() * 1.8:
            return None
        try:
            e = ce.Enemy(dict(enemy))
        except Exception:
            e = ce.Enemy(enemy)
        before = p.level
        try:
            ok = self.g._fight(e)
        except Exception as ex:
            self.log(f"  [AI] 战斗异常: {ex}")
            return False
        self.total_battles += 1
        fire(self.plugins, "on_battle_result", self, ok, enemy)
        if ok:
            if enemy.get("boss"):
                self.total_boss_wins += 1
                fire(self.plugins, "on_boss_kill", self, enemy)
            if p.level > before:
                self.last_level = p.level
                self.stuck_counter = 0
            return True
        self.total_deaths += 1
        return False

    # ================= 行为实现 =================

    def _fast_grind(self):
        """V6 高速刷怪：缓存当前区怪物池，零排序、战前回满 MP，逼近峰值吞吐"""
        p = self.g.p
        zi = p.zone
        if self._grind_zi != zi:
            pool = [m for m in self.zone_pool() if not m.get("boss")]
            if not pool:
                self.do_advance()
                return
            self._grind_pool = pool
            self._grind_zi = zi
        p.mp = p.max_mp
        self._fight_safe(random.choice(self._grind_pool))

    def do_upgrade(self):
        """练级：在当前区域刷怪（优先经验最高），若当前区无怪则尝试推进"""
        p = self.g.p
        if self.fast:
            self._fast_grind()
            return
        pool = self.zone_pool()
        if not pool:
            self.log(f"  [AI] 区域 {ce.ZONES[p.zone]['name']} 无怪物池，尝试推进")
            self.do_advance()
            return
        if p.hp < p.max_hp_full() * 0.55:
            self.do_rest()
            return
        # 经验最高的普通怪优先；低血量时选相对弱的怪
        hp_ratio = p.hp / max(1, p.max_hp_full())
        if hp_ratio < 0.75:
            cand = sorted(pool, key=lambda m: m.get("hp", 0))[:3]
        else:
            cand = sorted(pool, key=lambda m: -m.get("exp", 0))[:3]
        m = random.choice(cand)
        self._fight_safe(m)

    def _item_score(self, iid):
        it = ce.ITEM_MAP.get(iid) or {}
        t = it.get("type")
        base = it.get("atk", 0) * 1.6 + it.get("def", 0) * 1.4 + it.get("hp", 0) * 0.12
        base += it.get("agi", 0) * 0.5 + it.get("crit", 0) * 80 + it.get("dodge", 0) * 60
        if t == "weapon":
            base *= 1.0
        elif t == "armor":
            base *= 1.15
        elif t == "accessory":
            base *= 1.25
        return base, it

    def do_buy(self):
        """购装：从当前区商店找最佳装备并换上；买药补货"""
        p = self.g.p
        bought_any = False
        if not self.ensure_gold_floor():
            self.do_upgrade()
            return
        zone = ce.ZONES[p.zone]
        shop = zone.get("shop") or []
        want_types = {"weapon", "armor", "accessory"}
        candidates = []
        for iid in shop:
            it = ce.ITEM_MAP.get(iid)
            if not it or it.get("type") not in want_types:
                continue
            price = it.get("price", 0)
            if p.gold < price:
                continue
            sc, _ = self._item_score(iid)
            candidates.append((sc, iid, price))
        candidates.sort(reverse=True)
        slot_map = {"weapon": "weapon", "armor": "armor", "accessory": "accessory"}
        for sc, iid, price in candidates[:5]:
            it = ce.ITEM_MAP[iid]
            slot = slot_map[it["type"]]
            cur = getattr(p, slot)
            cur_sc, cur_it = self._item_score(cur) if cur else (0, None)
            if sc > cur_sc * 1.12:
                p.gold -= price
                p.inventory[iid] = p.inventory.get(iid, 0) + 1
                setattr(p, slot, iid)
                self.gear_bought += 1
                self.log(f"  [AI] 购入并穿戴 {it['name']}（评分 {int(sc)}）花费 {price}")
                bought_any = True
                p.stats["gold_earned"] = p.stats.get("gold_earned", 0)
        # 补药水
        if p.gold > 120 and sum(p.potions.values()) < 4:
            if self.buy_potion():
                self.log(f"  [AI] 补充治疗药水，当前 {sum(p.potions.values())} 瓶")
                bought_any = True
        if not bought_any:
            self.do_upgrade()

    def do_boss(self):
        """攻坚当前区守关 BOSS：先确保状态与血线门槛"""
        p = self.g.p
        specs = self.zone_boss_specs()
        if not specs:
            # 当前区无 BOSS：直接视为推进机会
            self.do_advance()
            return
        # 优先选还没讨伐过的 BOSS
        killed = set(p.bosses) | set(p.boss_kills.keys())
        fresh = [m for m in specs if m["name"] not in killed]
        if not fresh and self.aggressive:
            fresh = specs
        if not fresh:
            # 本区 BOSS 已清 -> 全图清剿：扫荡全局遗漏 BOSS（含模组/特殊 BOSS）
            allboss = [m for m in ce.MONSTERS if m.get("boss")]
            not_killed = [m for m in allboss if m["name"] not in killed]
            if not_killed:
                t = random.choice(not_killed) if len(not_killed) > 1 else not_killed[0]
                if t.get("dlc") and p.level < (getattr(RULES, "DLC_REQUIRED_LEVEL", None) or 90):
                    self.do_task()
                    return
                if p.hp < p.max_hp_full() * 0.60:
                    self.do_rest()
                    return
                self.log(f"  [AI] 全图清剿：讨伐遗漏 BOSS {t['name']}（HP {t.get('hp')}）")
                self._fight_safe(t)
                return
            # 全部打光 -> 推进
            self.do_advance()
            return
        target = fresh[0]
        if p.hp < p.max_hp_full() * (RULES.BOSS_MIN_HP_RATIO if RULES else 0.55):
            self.do_rest()
            return
        # 战前恢复满状态
        while self.auto_use_potion(0.95) and p.hp < p.max_hp_full() * 0.95:
            pass
        self.log(f"  [AI] ⚔ 挑战守关BOSS：{target['name']}（HP {target.get('hp')}）")
        ok = self._fight_safe(target)
        if ok:
            self.log(f"  [AI] 讨伐成功！{target['name']}")
            self.stuck_counter = 0
        elif ok is None:
            # V6.1：评估认为打不过（安全跳过），不封禁区域，练级后再来
            self.log(f"  [AI] 暂避 BOSS {target['name']}，练级后再战")
        else:
            # 失败 -> 冷却：标记该区暂缓，练级后重来
            self._zone_blacklist.add(p.zone)
            self.log(f"  [AI] BOSS 战失利，暂缓区域 {ce.ZONES[p.zone]['name']}，先练级")

    def do_advance(self):
        """推进区域：等级达标且下一区有怪物池才移动；白名单黑名单防跳空"""
        p = self.g.p
        # 先从黑名单里恢复（随等级提升解禁）
        new_black = set()
        for zi in self._zone_blacklist:
            z = ce.ZONES[zi]
            if p.level >= z.get("level", 0) + 12:
                continue
            new_black.add(zi)
        self._zone_blacklist = new_black
        cur = p.zone
        # 找下一个可行区域
        for zi in range(cur + 1, len(ce.ZONES)):
            z = ce.ZONES[zi]
            pool = z.get("monsters", [])
            if not pool:
                continue
            if zi in self._zone_blacklist:
                continue
            if p.level >= z.get("level", 0) + (RULES.ADVANCE_SAFETY_LEVEL if RULES else 3):
                # 推进条件：不低于推荐等级 - 容忍
                rec_level = z.get("level", 0)
                # 防止跳太远：只推进到最近可去区域
                p.zone = zi
                p.pos = [0, 0]
                self.zone_advanced += 1
                p.zone_visits[z["name"]] = p.zone_visits.get(z["name"], 0) + 1
                self.last_zone = zi
                self.stuck_counter = 0
                self.log(f"  [AI] 🚩 推进区域：Lv{p.level} 前往 {z['name']}（建议Lv{rec_level}）")
                return
            break
        # 无区域可推进：留在原地强化练级
        if p.level < 10:
            self.log(f"  [AI] 前期积累中（Lv{p.level}）")
        else:
            self.log(f"  [AI] 已到达当前可推进的最远区域（Lv{p.level}）")

    def do_rest(self):
        """休整：用药 -> 买药 -> 原地恢复"""
        p = self.g.p
        if self.fast:
            # V6 高速：直接大额恢复，减少休整轮数
            p.hp = min(p.max_hp_full(), p.hp + max(5, p.max_hp_full() // 3))
            return
        if self.auto_use_potion(0.7):
            self.log(f"  [AI] 休整：使用药水恢复至 HP {p.hp}")
            return
        if p.gold > 80:
            if self.buy_potion():
                self.log(f"  [AI] 休整：购买药水补给")
                return
        # 无药水无金币：低风险打怪（挑最弱）回血机会少，采用原地等待策略
        self.log(f"  [AI] 休整：HP {p.hp}/{p.max_hp_full()}，等待下一轮行动")
        p.hp = min(p.max_hp_full(), p.hp + max(1, p.max_hp_full() // 12))

    def do_craft(self):
        """锻造/合成：V6 提供安全强化钩子（不进入交互菜单）"""
        p = self.g.p
        # 若系统提供了自动强化 API 则调用；否则记录并回到练级
        auto = getattr(self.g, "auto_enhance", None)
        if callable(auto):
            try:
                ok = auto()
                if ok:
                    self.log(f"  [AI] 锻造强化成功")
                    return
            except Exception:
                pass
        # 合成兜底：用金币购买材料药水
        if p.gold > 200:
            self.buy_potion()
            self.log(f"  [AI] 锻造台休整：购入药水作为合成预备")
            return
        self.do_upgrade()

    def do_explore(self):
        """游历探索：移动拾取随机事件而不触发交互战斗"""
        p = self.g.p
        zone = ce.ZONES[p.zone]
        # 简单奇遇：根据区域种子随机奖励（安全、不入交互）
        r = random.random()
        p.pos = [random.randint(0, 149), random.randint(0, 149)]
        if r < 0.30:
            g = random.randint(20, 60 + p.level * 5)
            p.gold += g
            p.stats["gold_earned"] = p.stats.get("gold_earned", 0) + g
            self.log(f"  [AI] 探索 {zone['name']}：拾得金币 {g}")
        elif r < 0.55:
            xp = random.randint(15, 40 + p.level * 3)
            p.exp += xp
            p.total_exp_gained = getattr(p, "total_exp_gained", 0) + xp
            self.log(f"  [AI] 探索 {zone['name']}：获得经验 {xp}")
        elif r < 0.75:
            pots = [iid for iid, it in ce.ITEM_MAP.items() if it.get("type") == "potion" and it.get("heal")]
            if pots:
                iid = random.choice(pots)
                p.potions[iid] = p.potions.get(iid, 0) + 1
                self.log(f"  [AI] 探索 {zone['name']}：发现药水补给")
        else:
            # 遭遇弱怪战斗（自动）
            pool = [m for m in self.zone_pool() if not m.get("boss")]
            if pool:
                weak = sorted(pool, key=lambda m: m.get("hp", 0))[:2]
                self._fight_safe(random.choice(weak))
            else:
                self.do_upgrade()

    def do_task(self):
        """任务/图鉴整理：汇报收集进度，推进 DLC 目标"""
        p = self.g.p
        all_boss = [m["name"] for m in ce.MONSTERS if m.get("boss")]
        dlc_bosses = [m["name"] for m in ce.MONSTERS
                      if m.get("boss") and m.get("dlc")]
        killed = set(p.bosses) | set(p.boss_kills.keys())
        if dlc_bosses:
            left = [b for b in dlc_bosses if b not in killed]
            if left and p.level >= (getattr(RULES, "DLC_REQUIRED_LEVEL", None) or 90):
                # DLC 攻坚
                self._hunt_dlc_boss(left[0])
                return
        if len(killed) >= len(all_boss) - (len(dlc_bosses) if dlc_bosses else 0):
            self.log(f"  [AI] 图鉴整理：已讨伐 {len(killed)}/{len(all_boss)} BOSS，主线区域全通")
            # 满图鉴后扫尾：继续刷经验提升
            self.do_upgrade()
            return
        self.log(f"  [AI] 目标盘点：已讨伐 BOSS {len(killed)}/{len(all_boss)}"
                 + (f"，其中 DLC {len([b for b in killed if b in dlc_bosses])}/{len(dlc_bosses)}" if dlc_bosses else "")
                 + f"；当前区域 {ce.ZONES[p.zone]['name']} Lv{p.level}")
        # 缺 BOSS 时主动推进打 Boss
        self.do_boss()

    def _hunt_dlc_boss(self, name):
        """集中挑战 DLC 终极 BOSS：战前满状态 + 多轮攻坚"""
        p = self.g.p
        spec = next((m for m in ce.MONSTERS if m["name"] == name), None)
        if not spec:
            return
        while self.auto_use_potion(0.98) and p.hp < p.max_hp_full() * 0.98:
            pass
        self.log(f"  [AI] ⚔ 勇者之路 DLC 终极战：{name} 开战！")
        ok = self._fight_safe(spec)
        if ok:
            self.log(f"  [AI] 👑 DLC 讨伐成功：{name}！")
        else:
            self.log(f"  [AI] DLC 攻坚失败，继续积累实力")

    # ================= 自定义接入：API =================

    def ask_api(self, prompt):
        """外部 API 决策：失败自动回退本地规则（绝不阻塞主循环）"""
        if not self.api_url:
            return None
        try:
            import urllib.request
            body = json.dumps({
                "model": self.api_key.split(":")[0] if ":" in self.api_key else "auto",
                "prompt": prompt,
                "round": self.round,
                "player_level": self.g.p.level,
                "zone": self.g.p.zone,
            }).encode()
            req = urllib.request.Request(self.api_url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            if self.api_key:
                req.add_header("Authorization", "Bearer " + self.api_key)
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.loads(r.read().decode())
            action = data.get("action") or data.get("choice")
            if action in self.ACTIONS:
                return action
        except Exception:
            return None
        return None

    # ================= 自定义接入：MCP 服务 =================

    def _mcp_serve(self, port):
        """轻量 MCP 状态服务：GET /status 返回 JSON，POST /command 可暂停/存档"""
        try:
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
            ai = self

            class H(BaseHTTPRequestHandler):
                def log_message(self, *a):
                    pass

                def _send(self, obj, code=200):
                    body = json.dumps(obj, ensure_ascii=False).encode()
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def do_GET(self):
                    if self.path.startswith("/status"):
                        p = ai.g.p
                        self._send({
                            "status": "running", "round": ai.round,
                            "total_rounds": ai.rounds,
                            "state": ai._state,
                            "player": {"level": p.level, "gold": p.gold,
                                       "zone": p.zone, "hp": p.hp,
                                       "max_hp": p.max_hp_full(),
                                       "kills": p.kills,
                                       "boss_kills": len(p.boss_kills),
                                       "pet": p.pet},
                            "battles": ai.total_battles,
                            "boss_wins": ai.total_boss_wins,
                            "deaths": ai.total_deaths,
                            "save_file": ai.save_name,
                        })
                    elif self.path.startswith("/bosses"):
                        p = ai.g.p
                        self._send({"bosses": list(p.boss_kills.keys())[-50:]})
                    else:
                        self._send({"error": "not found"}, 404)

                def do_POST(self):
                    ln = int(self.headers.get("Content-Length") or 0)
                    raw = self.rfile.read(ln).decode() if ln else "{}"
                    try:
                        cmd = json.loads(raw or "{}").get("command")
                    except Exception:
                        cmd = None
                    if cmd == "save":
                        ai.save()
                        self._send({"ok": True, "msg": "已保存"})
                    elif cmd == "report":
                        self._send({"ok": True, "report": ai.summary_dict()})
                    else:
                        self._send({"error": "unknown command"}, 400)

            srv = ThreadingHTTPServer(("127.0.0.1", port), H)
            self._mcp = srv
            srv.serve_forever()
        except Exception as e:
            self.log(f"  [AI] MCP 服务启动失败: {e}")

    # ================= 存档与统计 =================

    def save(self):
        ce.SAVE_FILE = self.save_name
        self.g.save()
        p = self.g.p
        p.save_count = getattr(p, "save_count", 0) + 1
        fire(self.plugins, "on_save", self)

    def save_interval(self):
        """按阶段调整存档频率"""
        seg = self.segment()
        if RULES and seg in RULES.SAVE_STRATEGY:
            return RULES.SAVE_STRATEGY[seg]
        return 10 if seg >= 3 else (50 if seg == 1 else 20)

    def progress_stuck_check(self):
        """卡死检测：连续 10 回合无等级/区域/BOSS 变化则强制转向"""
        p = self.g.p
        if p.level > self.last_level or p.zone > self.last_zone:
            self.stuck_counter = 0
            self.last_level = p.level
            self.last_zone = p.zone
        elif len(p.bosses) + len(p.boss_kills) > self.last_bosses:
            self.stuck_counter = 0
            self.last_bosses = len(p.bosses) + len(p.boss_kills)
        else:
            self.stuck_counter += 1

    def maintenance(self):
        """深度维护：清点装备、买装、补药、考虑推进/攻坚"""
        p = self.g.p
        if getattr(self.g, "fast_mode", False):
            self.g.fast_settle()   # V6 高速模式：延迟补发掉落/成就后继续高速跑
            return
        self.do_buy()
        if p.hp < p.max_hp_full() * 0.5:
            self.do_rest()
        # 若领先当前区域等级较多且 BOSS 已清 -> 推进
        if p.level >= ce.ZONES[p.zone].get("level", 0) + 8:
            self.do_advance()

    def summary_dict(self):
        p = self.g.p
        return {
            "round": self.round,
            "total_rounds": self.rounds,
            "version": getattr(ce, "VERSION", "v5"),
            "player": {
                "name": p.name, "class": p.cls, "level": p.level,
                "gold": p.gold, "zone": p.zone,
                "zone_name": ce.ZONES[p.zone]["name"],
                "hp": p.hp, "max_hp": p.max_hp_full(),
                "kills": p.kills, "pet": p.pet,
                "bosses_killed": len(p.boss_kills),
                "boss_list": list(p.boss_kills.keys()),
                "stats": dict(p.stats),
                "total_exp_gained": getattr(p, "total_exp_gained", 0),
                "save_count": getattr(p, "save_count", 0),
            },
            "ai": {
                "battles": self.total_battles,
                "boss_wins": self.total_boss_wins,
                "deaths": self.total_deaths,
                "potion_bought": self.potion_bought,
                "gear_bought": self.gear_bought,
                "zone_advanced": self.zone_advanced,
                "state": self._state,
            },
        }

    def report(self):
        p = self.g.p
        lines = ["\n" + "=" * 58, "AI V6 游玩总结（%s）" % self.summary_dict()["version"]]
        lines.append(f"  回合 {self.round}/{self.rounds}  状态 {self._state}")
        lines.append(f"  最终等级 Lv{p.level}  金币 {p.gold}  击杀 {p.kills}"
                     f"  宠物 {p.pet or '无'}")
        lines.append(f"  区域进度：{ce.ZONES[p.zone]['name']}（第 {p.zone + 1}/{len(ce.ZONES)} 区）"
                     f"  推进次数 {self.zone_advanced}")
        lines.append(f"  已讨伐 BOSS {len(p.boss_kills)} 个：{', '.join(list(p.boss_kills.keys())[:20]) or '无'}")
        if len(p.boss_kills) > 20:
            lines.append(f"    … 等共 {len(p.boss_kills)} 个")
        lines.append(f"  AI 战斗 {self.total_battles} 场，胜利 BOSS {self.total_boss_wins} 场，"
                     f"阵亡 {self.total_deaths} 次")
        lines.append(f"  购装 {self.gear_bought} 件  补药 {self.potion_bought} 瓶")
        lines.append(f"  血量告急策略触发 {self.health_calls} 次")
        lines.append(f"  存档 {p.save_count} 次 -> {self.save_name}"
                     + ("（含 .gz 双格式）" if getattr(ce, "SAVE_GZIP", False) else ""))
        lines.append(f"  耗时 {self.elapsed:.1f} 秒  平均 {self.round / max(0.001, self.elapsed):.0f} 回合/秒")
        lines.append("=" * 58)
        text = "\n".join(lines)
        if not self.quiet:
            print(text)
        return text

    # ================= 主循环 =================

    def run(self):
        ce._AUTO_POTION = True   # V6.1：全自动战斗用药不再等待 stdin
        p = self.g.p
        if self.fast:
            self.g.fast_mode = True
            ce._FAST_QUIET = True
            self.quiet = True
        fire(self.plugins, "on_start", self)
        if not self.quiet:
            print(f"AI V6 开始：{p.name}（{p.cls}）Lv{p.level}"
                  f" 金币 {p.gold} 区域 {ce.ZONES[p.zone]['name']}"
                  f" 共 {self.rounds} 回合")
        start = time.time()
        maint = 20000 if self.fast else (RULES.MAINTENANCE_INTERVAL if RULES else 20)
        self.save()  # 启动先存一档
        for rnd in range(1, self.rounds + 1):
            self.round = rnd
            if self.max_sec and rnd % 100 == 0 and time.time() - start > self.max_sec:
                break
            if self.fast:
                # V6 高速引擎：跳过 API/规则矩阵，直接轻决策
                action = self.fast_action()
            else:
                action = self.ask_api(
                    f"苍穹远征V6 AI决策（回合{rnd}/等级{p.level}/金币{p.gold}/HP{p.hp}/{p.max_hp_full()}）"
                )
                if action is None:
                    action = self.choose_action()
            p.hp = min(p.max_hp_full(), p.hp)
            self._state = action
            getattr(self, self.ACTIONS[action])()
            fire(self.plugins, "on_round", self, rnd)
            self.progress_stuck_check()
            if rnd % (500 if self.long_run else maint) == 0:
                self.maintenance()
            iv = 4000 if self.fast else (2000 if self.long_run else self.save_interval())
            if rnd % iv == 0:
                self.save()
        self.save()
        self.elapsed = time.time() - start
        ce._FAST_QUIET = False
        text = self.report()
        return text


    def run_bench(self, rounds=20000):
        """V6 高速战斗基准：纯 _fast_fight 连战（回合=战斗回合），报峰值回合/秒"""
        p = self.g.p
        self.g.fast_mode = True
        ce._FAST_QUIET = True
        old_god, old_oh = p.god_mode, p.one_hit
        p.god_mode = True   # 规避死亡，基准聚焦战斗结算本身
        p.one_hit = False
        p.hp = p.max_hp_full(); p.mp = p.max_mp
        pool = [m for m in self.zone_pool() if not m.get("boss")]
        if not pool:
            pool = [ce.MONSTERS[0]]
        start = time.time()
        n = 0
        for _ in range(rounds):
            e = ce.Enemy(dict(random.choice(pool)))
            if self.g._fast_fight(e):
                n += 1
            p.hp = min(p.max_hp_full(), p.hp + max(1, p.max_hp_full() // 8))
            p.mp = p.max_mp
        el = time.time() - start
        p.god_mode, p.one_hit = old_god, old_oh
        ce._FAST_QUIET = False
        return n, el


def main():
    ap = argparse.ArgumentParser(description="苍穹远征 V6 AI 自动游玩引擎")
    ap.add_argument("--rounds", type=int, default=5000, help="游玩回合数（默认 5000）")
    ap.add_argument("--load", action="store_true", help="读取现有存档继续游玩")
    ap.add_argument("--save", default="starfall_save_v6.json", help="存档文件名")
    ap.add_argument("--quiet", action="store_true", help="安静模式")
    ap.add_argument("--long-run", action="store_true",
                    help="长时间挂机模式：稀疏存档/维护、日志裁剪")
    ap.add_argument("--max-sec", type=float, default=0,
                    help="最长游玩秒数（到达后自动存档结束，0 表示不限）")
    ap.add_argument("--aggressive", action="store_true", help="激进模式：更频繁挑战 BOSS")
    ap.add_argument("--plugins", default=DEFAULT_PLUGIN_DIR, help="插件目录")
    ap.add_argument("--api-url", default="", help="外部 API 决策地址（可选）")
    ap.add_argument("--api-key", default="", help="API Key（可选）")
    ap.add_argument("--mcp-port", type=int, default=0, help="启用 MCP 状态服务端口")
    ap.add_argument("--fast", action="store_true",
                    help="V6 高速引擎：轻决策+快速战斗+稀疏维护，吞吐可达万级回合/秒")
    ap.add_argument("--bench", type=int, nargs="?", const=20000, default=0,
                    help="高速战斗基准：连战 N 场输出峰值回合/秒（默认 20000）")
    args = ap.parse_args()

    ce.SAVE_FILE = args.save
    g = None
    if args.load and os.path.exists(args.save):
        g = ce.load_game()
        if g is None:
            print("存档读取失败，尝试旧格式迁移…")
    if g is None:
        cls_name = random.choice(list(ce.CLASSES.keys()))
        print(f"创建新 AI 角色（职业：{cls_name}）")
        g = ce.Game(ce.Player("AI勇者", cls_name))
        g.load_mods()
        g.experiment_mode = True

    pl = load_plugins(args.plugins)
    ai = AIPlayer(g, rounds=args.rounds, save_name=args.save,
                  quiet=(args.quiet or args.fast), plugins=pl, api_url=args.api_url,
                  api_key=args.api_key, mcp_port=args.mcp_port,
                  aggressive=args.aggressive, long_run=args.long_run,
                  max_sec=args.max_sec, fast=args.fast)
    if args.bench:
        ai.save()  # 基准前存档
        n, el = ai.run_bench(args.bench)
        print(f"[基准] {n} 场高速战斗耗时 {el:.2f}s → {n / el:.0f} 回合/秒（峰值基准）")
        return f"[基准] {n / el:.0f} 回合/秒"
    if args.mcp_port:
        t = threading.Thread(target=ai._mcp_serve, args=(args.mcp_port,), daemon=True)
        t.start()
        print(f"  [AI] MCP 状态服务已启动: http://127.0.0.1:{args.mcp_port}/status")
    text = ai.run()
    print(text)  # 无论是否 quiet 都把最终总结落日志/终端
    return text


if __name__ == "__main__":
    main()
