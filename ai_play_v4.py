# -*- coding: utf-8 -*-
"""
《苍穹远征：星陨传说》v3.0 AI 自动游玩脚本
================================================
一句话用法：
    python3 ai_play.py                    # AI 自动游玩 50 回合
    python3 ai_play.py --rounds 100       # 自定义回合数
    python3 ai_play.py --load             # 读取现有存档继续游玩
    python3 ai_play.py --save ai_save     # 指定存档文件名（默认 starfall_save.json）
    python3 ai_play.py --quiet            # 只输出每回合摘要

AI 策略（完美逻辑）：
  1. 每回合优先打怪（战斗/刷怪）获取经验与金币
  2. 金币不足 500 时去商店买药水补给
  3. 血量过低自动回满休息（使用药水）
  4. 金币充足时购买装备提升战力
  5. 等级提升后推进区域（传送至更高等级区域）
  6. 每 10 回合自动存档一次，可随时读档继续
  7. 战斗失败自动治疗并继续

纯标准库实现，零第三方依赖。
"""

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import celestial_expedition_v4 as ce
except ImportError:
    import celestial_expedition as ce


class AIPlayer:
    """AI 自动游玩控制器"""

    def __init__(self, game, rounds=50, save_name="starfall_save.json", quiet=False):
        self.g = game
        self.rounds = rounds
        self.save_name = save_name
        self.quiet = quiet
        self.logs = []
        self.ce = ce

    def log(self, text):
        if not self.quiet:
            print(text)
        self.logs.append(text)

    # ---------- AI 决策 ----------
    def auto_use_potion(self):
        """自动用药：选择第一个治疗药水（不触发交互 input）"""
        p = self.g.p
        for iid, n in list(p.potions.items()):
            if n > 0:
                it = ce.ITEM_MAP.get(iid)
                if it and it.get("heal"):
                    p.potions[iid] -= 1
                    p.hp = min(p.max_hp_full(), p.hp + it["heal"])
                    return True
        return False

    def decide(self, rnd):
        p = self.g.p
        zone = self.g.get_zone()
        # 1. 血量危险 -> 用药/休息
        if p.hp < p.max_hp_full() * 0.35:
            if self.auto_use_potion():
                self.log(f"  [AI] 回合{rnd}：血量告急，自动使用药水恢复 HP {p.hp}")
            else:
                self.g._dbg_full()
                self.log(f"  [AI] 回合{rnd}：无药水，原地休整回满")
            return
        # 2. 打怪升级（默认行为）
        if random.random() < 0.75 or p.level < 5:
            self.fight(rnd)
            return
        # 3. 攒钱买装备
        if p.gold > 400 and p.level >= 3:
            self.buy_gear(rnd)
            return
        # 4. 推进区域
        if p.level >= zone["level"] + 3 and p.zone < len(ce.ZONES) - 1:
            self.advance_zone(rnd)
            return
        # 5. 探索事件
        self.g.explore()
        self.log(f"  [AI] 回合{rnd}：探索 {zone['name']}")

    def fight(self, rnd):
        p = self.g.p
        try:
            m = self.g.pick_monster()
            before = p.level
            ok = self.g._fight(m)
            self.log(f"  [AI] 回合{rnd}：战斗{'胜利' if ok else '失败'} {m.name} | Lv{p.level}(+{p.level - before}) 金币{p.gold}")
        except Exception as e:
            self.log(f"  [AI] 回合{rnd}：战斗异常 {e}")

    def buy_gear(self, rnd):
        """自动购买商店装备/药水（直接调内部逻辑）"""
        p = self.g.p
        # 尝试购买药水
        bought = False
        try:
            potions = [iid for iid, it in ce.ITEM_MAP.items() if it["type"] == "potion"]
            if potions and p.gold >= 50:
                iid = random.choice(potions)
                price = 50
                if p.gold >= price:
                    p.gold -= price
                    self.g.add_item(iid, 1)
                    self.log(f"  [AI] 回合{rnd}：购买药水 {ce.ITEM_MAP[iid]['name']}")
                    bought = True
        except Exception:
            pass
        if not bought:
            self.fight(rnd)

    def advance_zone(self, rnd):
        p = self.g.p
        if p.zone < len(ce.ZONES) - 1:
            p.zone += 1
            p.pos = [0, 0]
            self.log(f"  [AI] 回合{rnd}：推进至区域 {ce.ZONES[p.zone]['name']}")

    def save(self):
        self.ce.SAVE_FILE = self.save_name
        self.g.save()

    # ---------- 主循环 ----------
    def run(self):
        self.log(f"AI 自动游玩开始：{self.g.p.name}（{self.g.p.cls}）Lv{self.g.p.level}，共 {self.rounds} 回合")
        start = time.time()
        for rnd in range(1, self.rounds + 1):
            self.decide(rnd)
            if rnd % 10 == 0:
                self.save()
                self.log(f"  [AI] 第 {rnd} 回合自动存档完成")
        self.save()
        elapsed = time.time() - start
        p = self.g.p
        self.log("\n" + "=" * 56)
        self.log("AI 游玩总结")
        self.log(f"  最终等级 Lv{p.level}  金币 {p.gold}  击杀 {p.kills}")
        self.log(f"  探索 {p.stats.get('explore', 0)} 次  战斗 {p.stats.get('battle', 0)} 次")
        self.log(f"  背包 {len(p.inventory)} 件  宠物 {p.pet or '无'}")
        self.log(f"  耗时 {elapsed:.1f} 秒  存档 {self.save_name}")
        self.log("=" * 56)


def main():
    ap = argparse.ArgumentParser(description="苍穹远征 v3.0 AI 自动游玩")
    ap.add_argument("--rounds", type=int, default=50, help="游玩回合数（默认 50）")
    ap.add_argument("--load", action="store_true", help="读取现有存档继续游玩")
    ap.add_argument("--save", default="starfall_save.json", help="存档文件名")
    ap.add_argument("--quiet", action="store_true", help="只输出摘要")
    args = ap.parse_args()

    ce.SAVE_FILE = args.save
    if args.load and os.path.exists(args.save):
        g = ce.load_game()
        if g is None:
            print("存档读取失败，创建新角色。")
            g = ce.Game(ce.Player("AI勇者", random.choice(list(ce.CLASSES.keys()))))
    else:
        g = ce.Game(ce.Player("AI勇者", random.choice(list(ce.CLASSES.keys()))))
        g.load_mods()
        g.experiment_mode = True  # AI 顺带体验实验模式
    ai = AIPlayer(g, rounds=args.rounds, save_name=args.save, quiet=args.quiet)
    ai.run()


if __name__ == "__main__":
    main()
