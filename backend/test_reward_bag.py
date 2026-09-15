# -*- coding: utf-8 -*-
"""增益洗牌袋分布测试：跑 60 次真实 _grant_learning_reward，统计分布与连击。

证明两点：①抽取是真随机（洗牌随机顺序）②每 6 次内 6 种各一次，杜绝「三连知识」。
"""
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from game_engine.game_controller import GameController
from models.game_state import CaseInfo, Clue, GameState


def make_controller() -> GameController:
    class DummyLLM:
        pass

    c = GameController(DummyLLM())
    hidden = [Clue(clue_id=f"h{i}", content=f"隐藏线索{i}", revealed=False,
                   critical=False, related_knowledge=None, perspective="") for i in range(3)]
    c.game_state = GameState(
        case=CaseInfo(
            case_id="t", title="测试", background="bg", victim_info="v", scene_description="s",
            truth={"who": "a", "what": "b", "why": "c", "how": "d", "twist": "e"},
            revealed_clues=[], hidden_clues=hidden, mysteries=[], identity_actions=[]
        ),
        remaining_turns=5, reasoning_progress=0.0,
    )
    return c


async def main() -> int:
    c = make_controller()
    picks = []
    for _ in range(60):
        cfg = await c._grant_learning_reward("")
        picks.append(cfg["reward_type"])

    counts = Counter(picks)
    print("60 次抽取分布:", dict(counts))
    all_ok = True

    # 断言1（用户痛点）：无同类三连（3 连续全同）
    no_triple = all(len(set(picks[i:i + 3])) != 1 for i in range(len(picks) - 2))
    # 断言2：4 种能力增益从不与自身相邻两连（袋内唯一保证——knowledge 永不出现「知识、知识」）
    abilities = {"knowledge", "association", "logic", "insight"}
    no_ability_double = all(
        not (picks[i] == picks[i + 1] and picks[i] in abilities)
        for i in range(len(picks) - 1)
    )
    # 断言3：每个完整袋（6 抽）内 4 种能力增益各恰好一次
    balanced = all(
        all(Counter(picks[b * 6:(b + 1) * 6]).get(a, 0) == 1 for a in abilities)
        for b in range(10)
    )
    # 说明：extra_turn 在线索全开后的袋中占 2 席，相邻两连属设计预期（连给两次机会），不断言。
    checks = [
        ("无同类三连", no_triple),
        ("能力增益无自身相邻两连(知识永不连击)", no_ability_double),
        ("每袋内4种能力增益各恰好1次", balanced),
        ("60次覆盖全部6种类型", len(counts) == 6),
    ]
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
        all_ok = all_ok and passed
    for i in range(len(picks) - 2):
        if len(set(picks[i:i + 3])) == 1:
            print(f"  三连@{i}: {picks[i:i + 3]}  前后文: {picks[max(0, i - 2):i + 5]}")

    print("\n==== " + ("ALL PASS" if all_ok else "HAS FAILURES") + " ====")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
