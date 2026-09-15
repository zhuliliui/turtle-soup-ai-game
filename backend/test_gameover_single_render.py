# -*- coding: utf-8 -*-
"""终局消息单渲染验证：mock 掉磁盘/等级写入与 LLM，直接调 _finalize_verification 断言 payload 结构。

修复前 bug：message（判定反馈+终局揭晓拼接）与 game_over_message 前端各渲染一次 → 终局内容重复两遍。
"""
import asyncio
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from game_engine.game_controller import GameController


def make_controller():
    class DummyLLM:
        pass

    c = GameController(DummyLLM())
    from models.game_state import CaseInfo, Clue, GameState
    c.game_state = GameState(
        case=CaseInfo(
            case_id="t", title="测试案件", background="bg", victim_info="v", scene_description="s",
            truth={"who": "王姐", "what": "杀陈老师", "why": "积怨", "how": "奖杯", "twist": "邻居是凶手"},
            revealed_clues=[Clue(clue_id="c1", content="线索1", revealed=True, critical=False,
                                 related_knowledge=None, perspective="")],
            hidden_clues=[], mysteries=[], identity_actions=[]
        ),
        remaining_turns=0, reasoning_progress=30.0,
    )
    return c


FAKE_VERIFICATION = {
    "completeness": 30,
    "errors": ["错误认为王姐杀了阿福"],
    "missing_points": ["备用钥匙手法"],
}


async def main() -> int:
    c = make_controller()
    log_calls = []
    with patch.object(c, "_save_to_disk", lambda: None), \
         patch.object(c, "_record_profile_result", lambda solved, level_gain=1: ""), \
         patch.object(c, "_append_log", lambda role, content: log_calls.append((role, content))):
        result = await c._finalize_verification("我的推理", FAKE_VERIFICATION)

    ok = True
    msg = result.get("message", "")
    gom = result.get("game_over_message", "")

    checks = [
        ("game_over=True", result.get("game_over") is True),
        ("case_solved=False", result.get("case_solved") is False),
        ("message 只含判定反馈(不含真相正文)", "真相：" not in msg and "⏱️ 推理机会已用尽" not in msg),
        ("message 含失败反馈", "否" in msg or "不符" in msg),
        ("game_over_message 含真相揭晓", "真相：" in gom and "⏱️ 推理机会已用尽" in gom),
        ("message 与 game_over_message 无内容重叠", gom.strip()[:50] not in msg),
        # 提交推理先记 user 流水，之后应为 ai(判定反馈) + ai(终局揭晓) 两条
        ("流水拆两条(判定反馈+终局揭晓)", len(log_calls) >= 2
         and all(r == "ai" for r, _ in log_calls[-2:])
         and "真相：" not in log_calls[-2][1] and "真相：" in log_calls[-1][1]),
    ]
    for name, passed in checks:
        ok = ok and passed
        print(f"{'PASS' if passed else 'FAIL'}  {name}")

    print("\n--- message (气泡) 开头 ---")
    print(msg[:120].replace("\n", " "))
    print("--- game_over_message (独立行) 开头 ---")
    print(gom[:120].replace("\n", " "))
    print("\n==== " + ("ALL PASS" if ok else "HAS FAILURES") + " ====")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
