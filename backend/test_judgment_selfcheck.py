# -*- coding: utf-8 -*-
"""判定自检提示词验证：不读写任何存档文件，纯内存构造案件后直接调 LLM。

用例（对应线上翻车场景《双面伪装》）：
  Q1 "阿福死了"          → 期望「否」（真相：阿福被王姐藏匿带走，没死）
  Q2 "阿福是王姐藏起来的吗" → 期望「是」（不过度拒绝）
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from ai_host.llm_client import LLMClient, LLMError, extract_json
from ai_host.reasoning_engine import ReasoningEngine
from models.game_state import CaseInfo, Clue, GameState


def build_state() -> GameState:
    case = CaseInfo(
        case_id="test-afu",
        title="双面伪装（自检测试）",
        background="小区保洁员王姐常替邻居陈老师遛金毛犬阿福，两人因遛狗报酬渐生矛盾。",
        victim_info="无人员伤亡，涉及宠物犬阿福",
        scene_description="陈老师家中门锁无损、物品翻动，阿福和牵引绳一起消失了。",
        truth={
            "who": "保洁员王姐",
            "what": "王姐持备用钥匙潜入陈老师家发生冲突，事后把金毛犬阿福藏匿带走，阿福并没有死",
            "why": "王姐与陈老师因遛狗报酬产生矛盾，心生不满",
            "how": "用备用钥匙开门潜入，离开时把阿福一起带走藏匿",
            "twist": "看似遇害/失踪的阿福其实被王姐藏匿，仍然活着",
        },
        revealed_clues=[
            Clue(clue_id="c1", content="阿福的牵引绳在王姐家中被发现",
                 revealed=True, critical=False, related_knowledge=None, perspective="")
        ],
        hidden_clues=[
            Clue(clue_id="c2", content="陈老师家的备用钥匙只有王姐有一把",
                 revealed=False, critical=True, related_knowledge=None, perspective="")
        ],
        mysteries=[],
        identity_actions=[],
    )
    return GameState(case=case, remaining_turns=7, reasoning_progress=57.1)


CASES = [
    ("阿福死了", "否"),
    ("阿福是王姐藏起来的吗", "是"),
]


async def main() -> int:
    llm = LLMClient()
    engine = ReasoningEngine(llm)
    state = build_state()
    all_ok = True

    # ===== 单元：死亡断言识别 =====
    assert engine._is_death_assertion("阿福死了")
    assert engine._is_death_assertion("王姐是不是把阿福杀死了")
    assert not engine._is_death_assertion("阿福是王姐藏起来的吗")
    assert not engine._is_death_assertion("牵引绳为什么在王姐家")
    print("单元: _is_death_assertion 识别 PASS")

    # ===== 单元：死亡核验调用（3 轮稳定性）=====
    verdicts = []
    for i in range(3):
        v = await engine._verify_death_claim(state, "阿福死了")
        verdicts.append(v or "(空)")
        print(f"单元: _verify_death_claim('阿福死了') 第{i+1}轮 = {verdicts[-1]}")
    ok = verdicts == ["未死亡"] * 3
    all_ok = all_ok and ok
    print(f"   {'PASS' if ok else 'FAIL'} (期望 3 轮全部 未死亡)")

    # ===== 端到端：走生产流式路径 process_inquiry_stream =====
    from models.game_state import InquiryType
    e2e_cases = [
        ("阿福死了", "否"),                 # 翻车场景：判定必须是 否
        ("阿福是王姐藏起来的吗", "是"),      # 不得误伤：正确答 是
    ]
    for question, expect in e2e_cases:
        for i in (1, 2):
            final_answer = None
            text_head = "(无输出)"
            try:
                async for kind, payload in engine.process_inquiry_stream(
                        state, InquiryType.QUESTION, question, None):
                    if kind == "final":
                        ai_response, state_updates = payload
                        final_answer = state_updates["revealed_info"][0]
                        text_head = ai_response.replace("\n", " ")[:80]
            except LLMError as e:
                final_answer = "RETRY_NEEDED"
                text_head = f"LLMError: {e}"
            ok = final_answer == expect
            all_ok = all_ok and ok
            print(f"\nE2E[{question}] 第{i}轮  期望={expect}  实际={final_answer}  {'PASS' if ok else 'FAIL'}")
            print(f"   权威回复: {text_head}")

    print("\n==== " + ("ALL PASS" if all_ok else "HAS FAILURES") + " ====")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
