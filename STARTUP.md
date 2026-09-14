# 海龟汤推理游戏 - 快速启动指南

## 启动方式（本地）

双击项目根目录的 `run_backend.bat`，启动后端服务（端口 8000）。

启动成功后浏览器打开：**http://localhost:8000** 即可游玩。

> 前端由后端直接托管，**无需单独启动前端服务**。

首次运行如缺依赖，手动安装一次即可：

```cmd
cd backend
pip install -r requirements.txt
```

## 访问地址

- **在线试玩（固定链接，推荐评委使用）**: https://15cd6151e0904833885706cd26a4793c.app.workbuddy.host
- 本地游戏界面: 双击 run_backend.bat 后打开 http://localhost:8000
- API文档: http://localhost:8000/docs

## 常见问题（FAQ）

### Q1：关机重启后，需要重新打开后端吗？

**需要。** 本地后端没有开机自启，电脑重启后：

1. 双击项目根目录的 `run_backend.bat`
2. 看到 `Application startup complete` 即启动成功
3. 浏览器打开 http://localhost:8000

**注意：云端固定链接不受你电脑开关机影响**——关机后评委仍可正常访问在线试玩地址。

### Q2：知乎真实登录在哪里发起？

**必须从云端正式站点发起**：https://15cd6151e0904833885706cd26a4793c.app.workbuddy.host

原因与流程说明：

- 知乎 OAuth 的回调地址登记在云端域名上。若从本地页面（localhost:8000）发起登录，授权码会回到云端而非本地，本地没有对应的 state，必然报「state 无效或已过期」。
- 后端已加**防呆拦截**：在本地页面点「知乎登录」会直接弹提示引导你去正式站点，不会再走到一半失败。
- 正确流程：打开云端站点 → 点「知乎登录」→ 跳转知乎授权页 → 点授权 → 自动回跳并提示「✅ 知乎授权登录成功」。

### Q3：演示模式是什么？

若后端未配置知乎 OAuth 凭证（`.env` 缺少 `ZHIHU_OAUTH_APP_ID` / `ZHIHU_OAUTH_APP_KEY`），点「知乎登录」会自动创建**演示会话**（演示玩家身份），不影响核心游戏体验——评委没有知乎账号也能完整游玩。

### Q4：端口被占用（Address already in use）

```cmd
netstat -ano | findstr :8000
taskkill /PID <进程ID> /F
```

然后重新双击 `run_backend.bat`。

### Q5：依赖安装失败 / ModuleNotFoundError

```cmd
python -m pip install --upgrade pip
cd backend
pip install -r requirements.txt --no-cache-dir
```

### Q6：API Key 未配置

检查 `backend\.env` 文件，确保包含：

```
ANTHROPIC_API_KEY=sk-ant-你的密钥
```

## 验证启动成功

后端窗口显示：

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

## 测试API

浏览器打开 http://localhost:8000/docs 查看交互式 API 文档。

现在开始游戏吧！
