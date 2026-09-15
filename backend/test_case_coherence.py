# -*- coding: utf-8 -*-
"""新约束实测：直接调 CaseGenerator 生成一个案件（纯内存，不碰 game_save.json），
检查 twist 颠覆性与背景伏笔闭合度。"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from ai_host.llm_client import LLMClient
from game_engine.case_generator import CaseGenerator

PREMISE = "食品厂由一对姐妹合办经营，外界只知道其中一人常代表公司处理事务"


async def main() -> int:
    gen = CaseGenerator(LLMClient())
    case, identity = await gen.generate_case_from_premise(PREMISE)
    print("标题:", case.title)
    print("玩家身份:", identity)
    print("\n=== 背景 ===")
    print(case.background)
    print("\n=== 现场 ===")
    print(case.scene_description)
    print("\n=== 真相 ===")
    t = case.truth or {}
    for k in ("who", "what", "why", "how", "twist"):
        print(f"[{k}] {t.get(k, '')}")
    print("\n=== 谜团 ===")
    for m in (case.mysteries or []):
        print("-", m)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
