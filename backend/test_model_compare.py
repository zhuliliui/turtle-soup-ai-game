# -*- coding: utf-8 -*-
"""候选模型横评：格式遵从（JSON 解析成功率）+ 判定正确率 + 反转创作力。

三个候选（网关 2026-09-14 实测 200 可用）：
  deepseek-v3.2 / gpt-5.4-mini / claude-sonnet-4-5-20250929
每模型：
  A. 提问判定 ×3（含翻车题「阿福死了」→否、防误伤「阿福是王姐藏起来的吗」→是、普通题）
  B. 案件真相创作 ×1（读 twist 是否有反转味，人工评估）
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from ai_host.llm_client import LLMClient, LLMError, extract_json
from ai_host.reasoning_engine import ReasoningEngine
from models.game_state import InquiryType
from test_judgment_selfcheck import build_state

CANDIDATES = [
    "deepseek-v3.2",
    "gpt-5.4-mini",
    "claude-sonnet-4-5-20250929",
]
if len(sys.argv) > 1:  # 命令行过滤：python test_model_compare.py claude
    CANDIDATES = [m for m in CANDIDATES if sys.argv[1] in m]

QUESTIONS = [
    ("阿福死了", "否"),
    ("阿福是王姐藏起来的吗", "是"),
    ("陈老师家的门锁有被撬的痕迹吗", "否"),  # 真相是备用钥匙开门，无撬痕
]

TRUTH_PROMPT = """你是海龟汤（情境猜谜）案件的编剧。请设计一桩案件真相，要求：
- 表面看是一桩普通事件，真相有一个**意料之外、情理之中**的反转
- 反转点必须由前文细节可以回溯推理出来，不能凭空冒出
只输出 JSON：
{"who": "真凶/关键人物", "what": "真正发生了什么", "why": "动机", "how": "手法", "twist": "反转点（一句话，要体现意料之外的翻转）", "surface": "表面看起来像什么"}"""


async def test_model(model: str) -> dict:
    llm = LLMClient(model=model)
    engine = ReasoningEngine(llm)
    state = build_state()
    parse_ok = correct = 0
    errors = []
    t0 = time.time()
    for q, expect in QUESTIONS:
        try:
            final_ans = None
            async for kind, payload in engine.process_inquiry_stream(state, InquiryType.QUESTION, q, None):
                if kind == "final":
                    final_ans = payload[1]["revealed_info"][0]
            parse_ok += 1
            correct += (final_ans == expect)
            if final_ans != expect:
                errors.append(f"[判定]{q}→{final_ans}(期望{expect})")
        except LLMError as e:
            errors.append(f"[解析失败]{q}: {str(e)[:60]}")
        except Exception as e:
            errors.append(f"[异常]{q}: {str(e)[:60]}")
    dt = time.time() - t0

    twist_text = ""
    try:
        raw = await llm.generate(TRUTH_PROMPT, max_tokens=500, temperature=0.9)
        data = extract_json(raw)
        if data:
            twist_text = str(data.get("twist", ""))[:120]
            surface = str(data.get("surface", ""))[:60]
        else:
            errors.append("[创作]truth JSON 解析失败")
    except Exception as e:
        errors.append("[创作]" + str(e)[:60])

    return {
        "model": model,
        "parse": f"{parse_ok}/3",
        "judge": f"{correct}/3",
        "sec": round(dt, 1),
        "twist": twist_text,
        "surface": surface if twist_text else "",
        "errors": errors,
    }


async def main():
    results = []
    for m in CANDIDATES:
        print(f"\n===== {m} =====")
        r = await test_model(m)
        results.append(r)
        print(f"解析成功率: {r['parse']}  判定正确: {r['judge']}  耗时: {r['sec']}s")
        for e in r["errors"]:
            print("  " + e)
        print(f"反转创作: {r['twist']}")
        if r["surface"]:
            print(f"(表面: {r['surface']})")
    print("\n===== 汇总 =====")
    for r in results:
        print(f"{r['model']}: 解析{r['parse']} 判定{r['judge']} {r['sec']}s")


if __name__ == "__main__":
    asyncio.run(main())
