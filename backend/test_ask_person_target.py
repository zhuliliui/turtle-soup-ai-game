# -*- coding: utf-8 -*-
"""「询问他人」身份锁定验证：
①单元：ASK_TARGET_PATTERN 解析（目标+问题拆分、排除「问题/问卷」误判）
②E2E：问陈屿→回复不得自称周远；问周远→回复必须是周远第一人称（跑3次取置信）
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from ai_host.llm_client import LLMClient, LLMError
from ai_host.reasoning_engine import ReasoningEngine
from models.game_state import CaseInfo, Clue, GameState


def build_state() -> GameState:
    case = CaseInfo(
        case_id="test-ask", title="写字楼疑云",
        background="某公司办公室深夜出事，员工周远与陈屿当晚都在场，两人各执一词。",
        victim_info="无人员伤亡，涉及公司机密文件",
        scene_description="办公室凌乱，内线电话倒在地上，合同散落一桌。",
        truth={
            "who": "周远",
            "what": "周远深夜潜回办公室销毁问题合同，被陈屿撞见",
            "why": "合同里的问题条款一旦被审计发现，周远将担责",
            "how": "借口让陈屿复核合同引开注意，趁乱处理文件",
            "twist": "看似老实巴交的周远才是当事人，陈屿只是无辜撞见者",
        },
        revealed_clues=[
            Clue(clue_id="c1", content="内线电话有被暴力扯拽的痕迹", revealed=True,
                 critical=False, related_knowledge=None, perspective="")
        ],
        hidden_clues=[], mysteries=[], identity_actions=[],
    )
    return GameState(case=case, user_identity="私家侦探", remaining_turns=5, reasoning_progress=20.0)


UNIT_CASES = [
    ("问周远：发生什么了", "周远", "发生什么了"),
    ("问陈屿：发生了什么", "陈屿", "发生了什么"),
    ("问问保安，昨晚谁进过楼", "保安", "昨晚谁进过楼"),
    ("请教医生：这伤怎么形成的", "医生", "这伤怎么形成的"),
]


async def main() -> int:
    all_ok = True

    # ===== 单元：正则解析 =====
    import re
    for text, want_t, want_q in UNIT_CASES:
        m = ReasoningEngine.ASK_TARGET_PATTERN.match(text)
        got = (m.group(1).strip(), m.group(2).strip()) if m else None
        ok = got == (want_t, want_q)
        all_ok = all_ok and ok
        print(f"{'PASS' if ok else 'FAIL'}  解析[{text}] -> {got}")
    for text in ("问题目难不难", "问卷填了吗"):
        ok = ReasoningEngine.ASK_TARGET_PATTERN.match(text) is None
        all_ok = all_ok and ok
        print(f"{'PASS' if ok else 'FAIL'}  排除[{text}]（应不匹配）")

    # ===== E2E：身份锁定 =====
    llm = LLMClient()
    engine = ReasoningEngine(llm)
    state = build_state()
    for target, other, question in (("陈屿", "周远", "发生了什么"), ("陈屿", "周远", "发生了什么"), ("周远", "陈屿", "发生什么了")):
        try:
            final = ""
            async for kind, payload in engine.generate_ask_person_stream(
                    state, f"问{target}：{question}"):
                if kind == "final":
                    final = payload
            head = final.replace("\n", " ")[:70]
            wrong_self = f"我是{other}" in final
            ok = (not wrong_self) and bool(final.strip())
            all_ok = all_ok and ok
            print(f"\n{'PASS' if ok else 'FAIL'}  问{target} -> 回复: {head}")
            if wrong_self:
                print(f"   !! 自称了{other}（身份漂移）")
        except LLMError as e:
            all_ok = False
            print(f"\nFAIL  问{target} -> LLMError: {str(e)[:60]}")

    print("\n==== " + ("ALL PASS" if all_ok else "HAS FAILURES") + " ====")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
