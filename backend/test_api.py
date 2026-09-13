# -*- coding: utf-8 -*-
"""端到端API测试脚本"""
import json
import sys
import time
import requests

BASE = "http://localhost:8000"
# 本地服务绕过系统代理
PROXIES = {"http": None, "https": None}


def post(path, payload, timeout=180):
    t0 = time.time()
    r = requests.post(f"{BASE}{path}", json=payload, proxies=PROXIES, timeout=timeout)
    dt = time.time() - t0
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:200]}
    print(f"\n>>> POST {path} -> {r.status_code} ({dt:.1f}s)")
    print(json.dumps(body, ensure_ascii=False, indent=1)[:1500])
    return r.status_code, body


def test_entertainment():
    print("=" * 60)
    print("[测试1] 娱乐模式：开始游戏")
    code, body = post("/api/game/start", {"identity": "侦探", "mode": "entertainment"})
    assert code == 200 and body.get("success"), f"开始游戏失败: {body}"
    game_id = body["data"]["game_id"]
    gs = body["data"]["game_state"]
    print(f"\n[OK] game_id={game_id}")
    print(f"[OK] 案件标题: {gs['case']['title']}")
    print(f"[OK] 初始线索数: {len(gs['case']['revealed_clues'])}")
    print(f"[OK] 剩余机会: {gs['remaining_turns']}")

    print("\n[测试2] 提问（LLM判断是/否）")
    code, body = post("/api/game/action", {
        "game_id": game_id, "action_type": "question",
        "content": "死者是自杀吗？"
    })
    assert code == 200 and body.get("success"), f"提问失败: {body}"
    print(f"\n[OK] AI回应: {body['data']['ai_response'][:100]}")
    turns_after_q = body["data"]["game_state"]["remaining_turns"]
    print(f"[OK] 提问后剩余机会: {turns_after_q}")

    print("\n[测试3] 提出猜想")
    code, body = post("/api/game/action", {
        "game_id": game_id, "action_type": "hypothesis",
        "content": "我认为凶手是因为利益纠纷下毒"
    })
    assert code == 200 and body.get("success"), f"猜想失败: {body}"
    print(f"\n[OK] 猜想反馈: {body['data']['ai_response'][:100]}")

    print("\n[测试4] 请求提示")
    code, body = post("/api/game/action", {
        "game_id": game_id, "action_type": "hint", "content": ""
    })
    assert code == 200 and body.get("success"), f"提示失败: {body}"
    print(f"\n[OK] 提示内容: {body['data']['hint'][:100]}")

    print("\n[测试5] 验证错误真相（应返回失败但success=true的业务结果）")
    code, body = post("/api/game/action", {
        "game_id": game_id, "action_type": "verification",
        "content": "凶手是图书馆馆长，为了争夺古籍珍藏而毒死了李明"
    })
    assert code == 200 and body.get("success"), f"验证失败: {body}"
    data = body["data"]
    print(f"\n[OK] 验证结果 success={data.get('success')}（False=没破案属正常）")
    print(f"[OK] message前120字: {data.get('message', '')[:120]}")
    assert "message" in data, "验证失败时应包含message给前端展示"

    print("\n[测试6] 获取游戏状态")
    r = requests.get(f"{BASE}/api/game/{game_id}/state", proxies=PROXIES, timeout=10)
    assert r.status_code == 200
    print(f"[OK] 状态码 {r.status_code}, 进度 {r.json()['data']['reasoning_progress']}%")

    print("\n[测试7] 无效game_id应返回404")
    code, body = post("/api/game/action", {
        "game_id": "not-exist", "action_type": "question", "content": "test"
    })
    assert code == 404, f"应返回404，实际{code}"
    print(f"[OK] 404 detail: {body.get('detail')}")

    return game_id


def test_learning():
    print("=" * 60)
    print("[测试8] 学习模式：开始游戏（知识点提取+案件生成）")
    code, body = post("/api/game/start", {
        "identity": "学生",
        "mode": "learning",
        "subject": "生物",
        "learning_content": "光合作用是绿色植物利用光能，将二氧化碳和水转化为有机物并释放氧气的过程。场所是叶绿体，分为光反应和暗反应两个阶段。"
    }, timeout=300)
    assert code == 200 and body.get("success"), f"学习模式开始失败: {body}"
    game_id = body["data"]["game_id"]
    print(f"\n[OK] 学习模式 game_id={game_id}")

    print("\n[测试9] 学习挑战（生成习题）")
    code, body = post("/api/game/action", {
        "game_id": game_id, "action_type": "learning", "content": ""
    }, timeout=180)
    assert code == 200 and body.get("success"), f"学习挑战失败: {body}"
    ex = body["data"]["exercise"]
    print(f"\n[OK] 题型: {ex['type']}, 知识点: {ex['knowledge_point']}")
    print(f"[OK] 题目: {ex['question'][:80]}")

    # 提交答案（选择题选A，判断题选对——无论对错，接口要正常返回）
    if ex["options"]:
        answer = "A" if ex["type"] == "single_choice" else "对"
    else:
        answer = "光合作用是植物利用光能合成有机物的过程"
    print(f"\n[测试10] 提交答案: {answer}")
    code, body = post("/api/game/exercise/submit", {
        "game_id": game_id, "answer": answer
    }, timeout=180)
    assert code == 200 and body.get("success"), f"提交答案失败: {body}"
    print(f"\n[OK] 评分反馈: {body['data'].get('message', '')[:100]}")

    return game_id


if __name__ == "__main__":
    t0 = time.time()
    gid1 = test_entertainment()
    gid2 = test_learning()

    # 清理测试游戏
    requests.delete(f"{BASE}/api/game/{gid1}", proxies=PROXIES, timeout=10)
    requests.delete(f"{BASE}/api/game/{gid2}", proxies=PROXIES, timeout=10)

    print("=" * 60)
    print(f"\n✅ 全部10项测试通过，总耗时 {time.time() - t0:.0f} 秒")
