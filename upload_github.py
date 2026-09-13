# -*- coding: utf-8 -*-
"""GitHub 一键上传（国内可达 api.github.com，无需 git push）

用法：
  set GITHUB_TOKEN=ghp_xxx && python upload_github.py [仓库名] [--private]

行为：
  1. 创建仓库（已存在则复用）
  2. 按 .gitignore 过滤本地文件
  3. Contents API 逐文件上传到 main 分支
"""
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from urllib.parse import quote

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
OWNER = None

# .gitignore 过滤规则（手工等价实现）
IGNORE_DIRS = {".git", ".workbuddy", ".claude", "__pycache__", ".venv", "venv", "node_modules"}
IGNORE_FILES = {".env", ".env.local", ".DS_Store", "Thumbs.db"}
IGNORE_SUFFIX = (".log", ".pyc", ".pyo")


def is_ignored(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for p in parts[:-1]:
        if p in IGNORE_DIRS or p == "data" and len(parts) > 1 and parts[0] == "backend":
            return True
    name = parts[-1]
    if name in IGNORE_FILES or name.endswith(IGNORE_SUFFIX):
        return True
    if name == ".env" or name.endswith(".env"):
        return True
    # backend/data/ 整目录排除
    rel = rel_path.replace("\\", "/")
    if rel.startswith("backend/data/"):
        return True
    return False


def collect_files():
    out = []
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, REPO_ROOT)
            if is_ignored(rel):
                continue
            out.append((full, rel.replace("\\", "/")))
    return out


def api_request(method: str, path: str, body: dict = None, raw: bool = False):
    url = API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + TOKEN,
        "User-Agent": "turtle-soup-uploader",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    try:
        r = urllib.request.urlopen(req, timeout=30)
        payload = r.read()
        return r.status, (payload if raw else json.loads(payload or b"{}"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    global OWNER
    if not TOKEN:
        print("错误：请先 set GITHUB_TOKEN=ghp_xxx")
        sys.exit(1)

    repo_name = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "turtle-soup-ai-game"
    is_private = "--private" in sys.argv

    # 1. 验证身份
    code, user = api_request("GET", "/user")
    if code != 200:
        print(f"Token 无效: {code} {user.get('message')}")
        sys.exit(1)
    OWNER = user["login"]
    print(f"[1/3] 身份验证 OK: {OWNER}")

    # 2. 创建仓库
    code, resp = api_request("POST", "/user/repos", {
        "name": repo_name,
        "description": "海龟汤推理游戏 - AI 互动推理 + 知乎 OAuth + 学习模式（知乎黑客松作品）",
        "private": is_private,
        "auto_init": False,
    })
    if code == 201:
        print(f"[2/3] 仓库已创建: {resp['html_url']}")
    elif code == 422:
        print(f"[2/3] 仓库已存在，复用: {OWNER}/{repo_name}")
    else:
        print(f"创建仓库失败: {code} {resp.get('message')}")
        sys.exit(1)

    # 3. 逐文件上传（已存在的文件先取 sha 再更新）
    files = collect_files()
    print(f"[3/3] 开始上传 {len(files)} 个文件...")
    fail = []
    for i, (full, rel) in enumerate(files, 1):
        with open(full, "rb") as f:
            content = base64.b64encode(f.read()).decode()

        # 预取 sha（文件已存在时必须携带才能更新）
        sha = None
        gcode, gresp = api_request("GET", f"/repos/{OWNER}/{repo_name}/contents/{quote(rel)}?ref=main")
        if gcode == 200:
            sha = gresp.get("sha")
            if sha and gresp.get("content") and gresp["content"].replace("\n", "") == content:
                print(f"  [{i}/{len(files)}] SKIP {rel} (内容未变)")
                continue

        body = {"message": f"upload: {rel}", "content": content, "branch": "main"}
        if sha:
            body["sha"] = sha
        code, resp = api_request("PUT", f"/repos/{OWNER}/{repo_name}/contents/{quote(rel)}", body)
        ok = code in (201, 200)
        size_kb = os.path.getsize(full) / 1024
        print(f"  [{i}/{len(files)}] {'OK ' if ok else 'FAIL'} {rel} ({size_kb:.1f}KB)")
        if not ok:
            fail.append((rel, code, resp.get("message", "")))
        time.sleep(0.4)

    print("\n========== 完成 ==========")
    print(f"仓库地址: https://github.com/{OWNER}/{repo_name}")
    if fail:
        print(f"失败 {len(fail)} 个:")
        for rel, c, m in fail:
            print(f"  {rel}: {c} {m}")
        sys.exit(2)
    print("全部上传成功 ✅")


if __name__ == "__main__":
    main()
