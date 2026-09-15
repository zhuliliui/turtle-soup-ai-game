# -*- coding: utf-8 -*-
"""知乎会话持久化验证：create → 落盘 → 清空内存(模拟重启) → load 恢复。

修复前 bug：会话只存进程内 dict，重启/重新部署后全部蒸发，刷新页面就得重新登录。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zhihu_integration as z


def main() -> int:
    ok = True
    tmp = os.path.join(tempfile.gettempdir(), "zhihu_sessions_test.json")
    z._SESSIONS_FILE = tmp  # 隔离，不碰真实 data/

    # 1) 建两个会话（一个 1 小时后过期，一个已过期）→ 应自动落盘且过期条目被清
    sid_keep = z._create_session("tok_keep", 3600, {"uid": "u1", "fullname": "玩家A"}, mock=False)
    sid_exp = z._create_session("tok_exp", -10, {"uid": "u2", "fullname": "过期者"}, mock=True)

    checks = []
    checks.append(("create 后落盘文件存在", os.path.exists(tmp)))
    import json as _json
    with open(tmp, "r", encoding="utf-8") as f:
        on_disk = _json.load(f)
    checks.append(("过期会话不进落盘文件", sid_exp not in on_disk and sid_keep in on_disk))

    # 2) 模拟重启：清空内存后从磁盘恢复
    z._sessions.clear()
    z._load_sessions()
    restored = z._sessions.get(sid_keep)
    checks.append(("重启后会话恢复", restored is not None))
    checks.append(("恢复内容完整(token/user)", bool(restored) and restored.get("access_token") == "tok_keep"
                   and restored.get("user", {}).get("fullname") == "玩家A"))
    checks.append(("过期会话重启后不复活", sid_exp not in z._sessions))

    # 3) logout 落盘：pop 后文件同步移除
    z._sessions.pop(sid_keep, None)
    z._persist_sessions()
    z._sessions.clear()
    z._load_sessions()
    checks.append(("logout 后重启不复活", sid_keep not in z._sessions))

    for name, passed in checks:
        ok = ok and passed
        print(f"{'PASS' if passed else 'FAIL'}  {name}")

    if os.path.exists(tmp):
        os.remove(tmp)
    print("\n==== " + ("ALL PASS" if ok else "HAS FAILURES") + " ====")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
