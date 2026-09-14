"""玩家个人资料 - 等级与完成案件记录（成功升级 / 失败降级）"""
import json
import os
import time
from typing import Dict

# 资料文件路径（与存档同目录：backend/data/player_profile.json）
# 注意：本文件在 backend/ 下，只需一层 dirname；game_controller.py 在 game_engine/ 下才需要两层
PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data", "player_profile.json"
)

MAX_RECORDS = 50  # 最多保留最近50条案件记录

# ============================================================
# 等级 → 开局资源（用户 2026-09-14 定稿）
#   线索：Lv1=3, Lv2=4, Lv3=5, Lv4=6, Lv5=7（每级 +1，Lv5 封顶 7 条）
#   推理次数：Lv1-5 固定 10 次；Lv6 起每级 +1（Lv6=11, Lv7=12…），封顶 20 次
# ============================================================
BASE_CLUE_COUNT = 3      # Lv.1 的线索数
MAX_CLUE_COUNT = 7       # 线索封顶（Lv5 达到）
BASE_TURNS = 10          # Lv.1-5 的推理机会
TURNS_START_LEVEL = 6    # 推理次数从 Lv6 开始增长
MAX_TURNS = 20           # 推理次数封顶


def clue_count_for_level(level: int) -> int:
    """按等级计算开局线索数量：Lv1→3, Lv2→4 … Lv5+→7（封顶）"""
    lv = max(1, int(level or 1))
    return min(BASE_CLUE_COUNT + (lv - 1), MAX_CLUE_COUNT)


def turns_for_level(level: int) -> int:
    """按等级计算推理机会：Lv1-5→10；Lv6→11, Lv7→12 … 封顶 20"""
    lv = max(1, int(level or 1))
    if lv < TURNS_START_LEVEL:
        return BASE_TURNS
    return min(BASE_TURNS + (lv - TURNS_START_LEVEL + 1), MAX_TURNS)


def _empty_profile() -> Dict:
    return {"level": 1, "wins": 0, "losses": 0, "records": []}


def load_profile() -> Dict:
    """读取个人资料，文件缺失或损坏时返回初始资料"""
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        profile = _empty_profile()
        profile["level"] = max(1, int(data.get("level", 1)))
        profile["wins"] = max(0, int(data.get("wins", 0)))
        profile["losses"] = max(0, int(data.get("losses", 0)))
        records = data.get("records", [])
        profile["records"] = records if isinstance(records, list) else []
        return profile
    except Exception:
        return _empty_profile()


def save_profile(profile: Dict) -> None:
    """原子写入，避免写一半损坏"""
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    tmp = PROFILE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROFILE_PATH)


def record_game_result(*, solved: bool, case_title: str, identity: str,
                       mode: str, progress: float, turns_used: int,
                       level_gain: int = 1) -> Dict:
    """结算一局：成功按还原度升级（>60 升1级，>80 优秀升2级），失败 -1 级（最低 Lv.1），写入案件记录

    level_gain: 成功时的升级级数（1=普通成功，2=优秀）
    返回 {"profile": 资料全量, "note": 等级变化提示文案, "old_level": 结算前等级}
    """
    profile = load_profile()
    old_level = profile["level"]

    if solved:
        profile["wins"] += 1
        gain = max(1, int(level_gain or 1))
        profile["level"] = old_level + gain
        if gain >= 2:
            note = f"🌟 完美还原！个人等级大幅提升：Lv.{old_level} → Lv.{profile['level']}（+{gain}）"
        else:
            note = f"📈 个人等级提升：Lv.{old_level} → Lv.{profile['level']}"
    else:
        profile["losses"] += 1
        profile["level"] = max(1, old_level - 1)
        if profile["level"] < old_level:
            note = f"📉 个人等级下降：Lv.{old_level} → Lv.{profile['level']}"
        else:
            note = "个人等级已是最低，保持 Lv.1"

    profile["records"].append({
        "title": case_title or "未命名案件",
        "identity": identity or "未知身份",
        "mode": mode or "entertainment",
        "result": "win" if solved else "lose",
        "progress": round(float(progress or 0), 1),
        "turns_used": int(turns_used or 0),
        "ts": time.time()
    })
    profile["records"] = profile["records"][-MAX_RECORDS:]
    save_profile(profile)
    return {"profile": profile, "note": note, "old_level": old_level}
