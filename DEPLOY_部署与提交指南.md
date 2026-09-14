# ⑤ → ⑬ CloudStudio 部署 + 知乎配置操作指南

> GitHub 已就绪：**https://github.com/zhuliliui/turtle-soup-ai-game**
> 目标：把 Demo 从「本机 Funnel（电脑必须开机）」迁到 CloudStudio（云端常驻，电脑可关）

---

## ⑤ CloudStudio 从 GitHub 拉代码

1. 打开 CloudStudio（cloudstudio.net），进入你的工作空间（新建一个也可以）
2. 打开终端（Terminal → New Terminal）
3. 执行：
   ```bash
   git clone https://github.com/zhuliliui/turtle-soup-ai-game.git
   cd turtle-soup-ai-game
   ```
   - 若 GitHub 拉取慢/失败，改用镜像：
   ```bash
   git clone https://gh-proxy.com/https://github.com/zhuliliui/turtle-soup-ai-game.git
   cd turtle-soup-ai-game
   ```

## ⑥ CloudStudio 配真实 API Key

```bash
cd backend
cp .env.example .env
# 用编辑器打开 .env，填两行：
#   ANTHROPIC_API_KEY=你的真实key（就是本机 backend/.env 里那串）
#   API_BASE_URL=https://api.openai-next.com
```
> `.env` 已被 .gitignore 排除，不会被传回 GitHub。工作空间重建会丢，记得自己留个备份。

## ⑦ 跑起来

```bash
pip install -r backend/requirements.txt
cd backend
python main.py
```
看到 `Uvicorn running on http://0.0.0.0:8000` 即成功。
> ⚠️ 注意启动日志会打印 `ANTHROPIC_API_KEY 已配置（sk-NKi****）`——确认是你自己的 key。

## ⑧ 得到公网 Demo URL

1. CloudStudio 界面右侧/底部的**「端口」面板**（Ports）
2. 添加/暴露端口 **8000**，选择**公网访问/对外预览**
3. 面板会给出一个 `https://xxx-8000.cloudstudio...` 形式的公网 HTTPS 地址
4. 手机浏览器打开验证：能看到开局页面 ✅

> 免费工作空间闲置会自动休眠，演示/评审前先打开激活一下。这个 URL 就是你的 **Demo 作品链接**。

## ⑨ 知乎创建项目

1. 打开知乎黑客松活动页（赛事报名页）
2. 「创建项目」，填名称/简介（简介可参考 README.md）

## ⑩ 填 Demo / GitHub / OAuth Callback

| 字段 | 填什么 |
|---|---|
| 作品链接（Demo） | ⑧ 得到的 CloudStudio 公网 URL |
| GitHub 链接 | `https://github.com/zhuliliui/turtle-soup-ai-game` |
| OAuth 回调地址 | `你的DemoURL` + `/api/zhihu/callback`（例如 `https://xxx-8000.cloudstudio.workstations.pro/api/zhihu/callback`） |

> ⚠️ 回调地址必须与这里登记的**一字不差**（协议、域名、端口、路径都要完全一致）。

## ⑪ 拿 App ID + App Key

项目创建/登记后，在活动页项目详情里领取 `App ID` 和 `App Key`。

## ⑫ 把知乎凭证放进 CloudStudio 环境变量

编辑 `backend/.env`，追加三行：

```
ZHIHU_OAUTH_APP_ID=领到的AppID
ZHIHU_OAUTH_APP_KEY=领到的AppKey
ZHIHU_OAUTH_REDIRECT_URI=第⑩步登记的完整回调地址
```

然后重启后端：终端里 `Ctrl+C` 停掉 → 重新 `python main.py`。
> 重启后前端不再显示「演示登录」字样，即为凭证生效。

## ⑬ 测试知乎登录

1. 手机/电脑浏览器打开 Demo URL
2. 点「知乎账号」条 → **登录** → 跳转知乎授权页 → 同意
3. 回到游戏页显示真实知乎昵称/头像 ✅
4. 「知乎故事改编」开局拉一次真实故事列表 ✅

---

## 全部通过后

- 回知乎活动页**提交作品**（截止 **9/15 10:00**，别拖到最后一晚）
- **提交完成后立刻作废这个 PAT**：github.com → Settings → Developer settings → Tokens (classic) → Delete（token 已在聊天中明文出现过，用完必删）
- 同理，提交评审结束后建议在活动页重置 App Key（赛事安全要求）

## 出问题时自查

| 症状 | 检查 |
|---|---|
| 打不开 Demo | 后端进程还活着吗；端口面板 8000 是否还是公网状态 |
| 登录后报回调错误 | `.env` 的 REDIRECT_URI 与活动页登记是否完全一致 |
| AI 无响应/报错 | `.env` 的 API_BASE_URL / ANTHROPIC_API_KEY 是否填对；启动日志是否「已配置」 |
| 知乎故事拉不到 | 先单独测 `curl https://api.zhihu.com/...`（赛事内容API）；CloudStudio 出网一般无碍 |
