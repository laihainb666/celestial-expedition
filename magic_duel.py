# -*- coding: utf-8 -*-
"""
魔法对决 (Magic Duel) —— 基于《通用游戏AI逻辑模板》实现的小游戏

模板四件套:
  状态抽象 State  ->  RPGState（双方血量/蓝量/技能冷却/护盾，回合真正交替）
  动作空间 Action ->  技能表 SKILLS（数据驱动）
  决策策略 Policy ->  Random / Greedy / Minimax / Script / Aggressive（可插拔）
  评估函数        ->  RPGState.evaluate（血量差 + 技能就绪 + 资源 + 护盾）

玩法:
  1. 人机对战: 你 vs AI，选择难度（简单=随机 / 普通=贪心 / 困难=Minimax）
  2. AI 自对战: 两种策略自动打 N 局，统计胜率，验证"策略越好胜率越高"
"""

import math
import random
import sys
from abc import ABC, abstractmethod
from typing import List, Optional


# ============================================================
# 1. 技能表（数据驱动，模板第 6 节最佳实践）
# ============================================================
SKILLS = [
    {"name": "平砍",   "dmg": 20, "mp_cost": 0,  "cd": 0},
    {"name": "冰锥术", "dmg": 40, "mp_cost": 15, "cd": 1},
    {"name": "火球术", "dmg": 60, "mp_cost": 30, "cd": 2},
    {"name": "治愈术", "heal": 50, "mp_cost": 25, "cd": 3},
    {"name": "护盾",   "shield": 30, "mp_cost": 20, "cd": 2},
    {"name": "雷击",   "dmg": 90, "mp_cost": 50, "cd": 4},
]


# ============================================================
# 2. 模板骨架: GameState / Action / Strategy / AIAgent / play_game
# ============================================================
class Action(ABC):
    """动作：AI / 玩家可执行的单一操作"""

    def __init__(self, name: str = ""):
        self.name = name

    def __repr__(self):
        return f"Action({self.name})"


class GameState(ABC):
    """游戏状态抽象：任何游戏实现 5 个方法即可接入全部策略"""

    @abstractmethod
    def current_player(self) -> int:
        pass

    @abstractmethod
    def get_legal_actions(self) -> List[Action]:
        pass

    @abstractmethod
    def apply_action(self, action: Action) -> "GameState":
        pass

    @abstractmethod
    def is_terminal(self) -> bool:
        pass

    @abstractmethod
    def get_winner(self) -> Optional[int]:
        pass

    @abstractmethod
    def evaluate(self, player: int) -> float:
        pass


class Strategy(ABC):
    """策略基类：输入状态，输出动作"""

    @abstractmethod
    def decide(self, state: GameState, player: int) -> Action:
        pass


class RandomStrategy(Strategy):
    """随机策略：测试与不确定性"""

    def decide(self, state, player):
        return random.choice(state.get_legal_actions())


class GreedyStrategy(Strategy):
    """贪心策略：一步评估，选最高分"""

    def decide(self, state, player):
        best_action, best_score = None, -math.inf
        for action in state.get_legal_actions():
            score = state.apply_action(action).evaluate(player)
            if score > best_score:
                best_score, best_action = score, action
        return best_action


class MinimaxStrategy(Strategy):
    """Minimax + Alpha-Beta 剪枝：向前推演 depth 层（模板第 3.4 节）"""

    def __init__(self, depth: int = 4):
        self.depth = depth

    def decide(self, state, player):
        best_action, best_score = None, -math.inf
        alpha, beta = -math.inf, math.inf
        for action in state.get_legal_actions():
            # apply 后轮到对手，因此下一层是对手回合(min层)
            score = self._minimax(state.apply_action(action, deterministic=True),
                                  self.depth - 1, alpha, beta, True, player)
            if score > best_score:
                best_score, best_action = score, action
            alpha = max(alpha, best_score)
        return best_action

    def _minimax(self, state, depth, alpha, beta, is_minimizing, player):
        if depth == 0 or state.is_terminal():
            return state.evaluate(player)
        actions = state.get_legal_actions()
        if is_minimizing:
            value = math.inf
            for action in actions:
                value = min(value, self._minimax(
                    state.apply_action(action, deterministic=True),
                    depth - 1, alpha, beta, False, player))
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return value
        value = -math.inf
        for action in actions:
            value = max(value, self._minimax(
                state.apply_action(action, deterministic=True),
                depth - 1, alpha, beta, True, player))
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value


class ScriptStrategy(Strategy):
    """脚本策略：给 NPC 用的固定规则（雷击可用就放雷击，否则平砍）"""

    def decide(self, state, player):
        for i, sk in enumerate(SKILLS):
            if sk["name"] == "雷击" and state.cds[player][i] == 0 \
               and state.mp[player] >= sk["mp_cost"]:
                return Action("雷击")
        return Action("平砍")


class AggressiveStrategy(GreedyStrategy):
    """激进性格：只看即时伤害（模板第 6.3 节）"""

    def decide(self, state, player):
        return max(state.get_legal_actions(),
                   key=lambda a: next(s.get("dmg", 0) for s in SKILLS
                                      if s["name"] == a.name))


class AIAgent:
    """通用 AI 智能体：名字 + 玩家编号 + 策略"""

    def __init__(self, name: str, player: int, strategy: Strategy):
        self.name = name
        self.player = player
        self.strategy = strategy

    def decide(self, state: GameState) -> Action:
        return self.strategy.decide(state, self.player)


def play_game(initial_state: GameState, agents: List[AIAgent],
              max_rounds: int = 1000, verbose: bool = True) -> Optional[int]:
    """通用对局调度器：任何实现 GameState 的游戏都能用它对局"""
    state = initial_state
    round_no = 0
    while not state.is_terminal() and round_no < max_rounds:
        agent = agents[state.current_player()]
        action = agent.decide(state)
        if verbose:
            print(f"  回合{round_no + 1}: {agent.name} -> {action.name}")
        state = state.apply_action(action)
        round_no += 1
    winner = state.get_winner()
    if verbose:
        if winner is not None:
            print(f"  对局结束! 胜者: {agents[winner].name}")
        else:
            print("  对局结束! 平局 / 达最大回合。")
    return winner


# ============================================================
# 3. 具体游戏: RPG 魔法对决（模板第 6 节完整实现）
# ============================================================
class RPGState(GameState):
    """状态: 双方(0号玩家/1号玩家) 血量/蓝量/护盾/技能冷却，回合交替"""

    def __init__(self, hp=None, mp=None, shield=None, cds=None,
                 turn=0, current=0):
        self.hp = hp if hp is not None else [100, 120]
        self.mp = mp if mp is not None else [100, 100]
        self.shield = shield if shield is not None else [0, 0]
        self.cds = cds if cds is not None else [[0] * len(SKILLS),
                                                [0] * len(SKILLS)]
        self.turn = turn
        self.current = current  # 0 或 1，谁行动

    def current_player(self):
        return self.current

    def get_legal_actions(self, player=None):
        p = self.current if player is None else player
        acts = []
        for i, sk in enumerate(SKILLS):
            if self.cds[p][i] == 0 and self.mp[p] >= sk.get("mp_cost", 0):
                acts.append(Action(sk["name"]))
        return acts if acts else [Action("平砍")]

    def apply_action(self, action, deterministic=False):
        """执行动作 -> 新状态（只执行当前玩家动作，然后切换回合）"""
        p = self.current
        enemy = 1 - p
        hp = self.hp[:]
        mp = self.mp[:]
        shield = self.shield[:]
        cds = [row[:] for row in self.cds]

        i = next(i for i, sk in enumerate(SKILLS) if sk["name"] == action.name)
        sk = SKILLS[i]
        mp[p] -= sk.get("mp_cost", 0)
        if sk.get("dmg"):
            dmg = sk["dmg"] if deterministic else sk["dmg"] + random.randint(-4, 5)
            if shield[enemy] > 0:           # 护盾先吸收伤害
                absorb = min(shield[enemy], dmg)
                shield[enemy] -= absorb
                dmg -= absorb
            hp[enemy] = max(0, hp[enemy] - dmg)
        if sk.get("heal"):
            hp[p] = min(120, hp[p] + sk["heal"])
        if sk.get("shield"):
            shield[p] = min(60, shield[p] + sk["shield"])
        cds[p] = [max(0, c - 1) for c in cds[p]]
        cds[p][i] = sk["cd"]

        return RPGState(hp, mp, shield, cds, self.turn + 1, enemy)

    def is_terminal(self):
        return self.hp[0] <= 0 or self.hp[1] <= 0

    def get_winner(self):
        if self.hp[0] <= 0:
            return 1
        if self.hp[1] <= 0:
            return 0
        return None

    def evaluate(self, player):
        """评估函数（模板核心）: 血量差 + 大招就绪 + 蓝量 + 护盾 + 终局大分"""
        enemy = 1 - player
        score = (self.hp[player] - self.hp[enemy]) * 1.0
        score += self.shield[player] * 0.3 - self.shield[enemy] * 0.3
        score += self.mp[player] * 0.05 - self.mp[enemy] * 0.02
        for i, sk in enumerate(SKILLS):
            if sk["name"] in ("火球术", "雷击") and self.cds[player][i] == 0:
                score += 6
            if sk["name"] in ("火球术", "雷击") and self.cds[enemy][i] == 0:
                score -= 6
        if self.is_terminal():
            score += 1000 if self.get_winner() == player else -1000
        return score

    def render(self, names=("你", "敌人")):
        print("-" * 52)
        print(f"回合 {self.turn + 1}  当前行动: {names[self.current]}")
        for p in (0, 1):
            ready = ", ".join(SKILLS[i]["name"] for i in range(len(SKILLS))
                              if self.cds[p][i] == 0 and self.mp[p] >= SKILLS[i]["mp_cost"])
            print(f"  {names[p]}: HP {self.hp[p]:>3}  MP {self.mp[p]:>3}  "
                  f"护盾 {self.shield[p]:>2}  | 可用: {ready}")
        print("-" * 52)


# ============================================================
# 4. 人机对战模式（玩家手动操作）
# ============================================================
def human_vs_ai(strategy_name: str):
    strategy = {
        "简单": RandomStrategy(),
        "普通": GreedyStrategy(),
        "困难": MinimaxStrategy(depth=4),
    }[strategy_name]

    ai = AIAgent(f"AI[{strategy_name}]", player=1, strategy=strategy)
    state = RPGState()
    print(f"\n===== 魔法对决: 你 vs {ai.name} =====")
    print("你(0) HP100/MP100；敌人(1) HP120/MP100。双方轮流行动，谁血先归零谁输。")

    while not state.is_terminal():
        state.render()
        if state.current_player() == 0:
            legal = state.get_legal_actions()
            names = [a.name for a in legal]
            print(f"请选择技能 {list(enumerate(names))} (q 退出): ", end="")
            line = input().strip().lower()
            if line in ("q", "quit", "exit"):
                print("你逃跑了……")
                return
            if not line.isdigit() or int(line) not in range(len(names)):
                print("输入无效，请重新选择。")
                continue
            action = legal[int(line)]
        else:
            action = ai.decide(state)
            print(f"{ai.name} 选择 -> {action.name}")
        state = state.apply_action(action)

    state.render()
    winner = state.get_winner()
    if winner == 0:
        print("胜利！你击败了敌人！")
    else:
        print("失败……敌人太强了。")


# ============================================================
# 5. AI 自对战模式（策略对比验证）
# ============================================================
def ai_vs_ai(strategy_a: str, strategy_b: str, games: int = 200, verbose=False):
    makers = {
        "随机": lambda: RandomStrategy(),
        "贪心": lambda: GreedyStrategy(),
        "脚本": lambda: ScriptStrategy(),
        "激进": lambda: AggressiveStrategy(),
        "搜索": lambda: MinimaxStrategy(depth=3),
    }
    wins_a = wins_b = draws = 0
    half = games // 2
    # 公平配对：A 先手 half 局，B 先手 half 局
    for _ in range(half):
        winner = play_game(RPGState(),
                           [AIAgent(f"A[{strategy_a}]", 0, makers[strategy_a]()),
                            AIAgent(f"B[{strategy_b}]", 1, makers[strategy_b]())],
                           max_rounds=60, verbose=verbose)
        if winner == 0:
            wins_a += 1
        elif winner == 1:
            wins_b += 1
        else:
            draws += 1
    for _ in range(games - half):
        winner = play_game(RPGState(),
                           [AIAgent(f"B[{strategy_b}]", 0, makers[strategy_b]()),
                            AIAgent(f"A[{strategy_a}]", 1, makers[strategy_a]())],
                           max_rounds=60, verbose=verbose)
        if winner == 0:
            wins_b += 1
        elif winner == 1:
            wins_a += 1
        else:
            draws += 1
    total = wins_a + wins_b + draws
    print(f"\n===== {strategy_a} vs {strategy_b}  ({games} 局, 轮流先手) =====")
    print(f"  {strategy_a}: {wins_a} 胜 ({wins_a / total * 100:.1f}%)")
    print(f"  {strategy_b}: {wins_b} 胜 ({wins_b / total * 100:.1f}%)")
    print(f"  平局: {draws} ({draws / total * 100:.1f}%)")
    print(f"  -> 胜率结论: {strategy_a if wins_a >= wins_b else strategy_b} 更强\n")


def main():
    print("""
============================================
  魔法对决 Magic Duel
  基于《通用游戏AI逻辑模板》的小游戏
============================================
  1. 人机对战（简单/普通/困难）
  2. AI 自对战（策略对比，验证 AI 强弱）
  3. 退出
""")
    while True:
        try:
            choice = input("请选择模式: ").strip()
        except EOFError:
            break
        if choice == "1":
            print("选择难度: 1.简单(随机) 2.普通(贪心) 3.困难(Minimax)")
            diff = input("难度: ").strip()
            if diff == "1":
                human_vs_ai("简单")
            elif diff == "2":
                human_vs_ai("普通")
            elif diff == "3":
                human_vs_ai("困难")
            else:
                print("无效难度。")
        elif choice == "2":
            ai_vs_ai("随机", "贪心")
            ai_vs_ai("贪心", "搜索")
            ai_vs_ai("脚本", "搜索")
        elif choice == "3":
            print("再见！")
            sys.exit(0)
        else:
            print("无效输入。")


if __name__ == "__main__":
    main()
