# MEMORY.md — 海龟汤项目长期约定

## 项目概况
- 路径：`C:\Users\zhu\Desktop\海龟汤`
- 前端：**单文件** `frontend/index.html`（HTML+CSS+JS 全内联，约 2700 行）。勿拆分为框架工程。
- 后端：`backend/`（Python，FastAPI 风格，API_BASE 逻辑：https 或 8000 端口时同源，否则 `http://localhost:8000`）。
- 视觉基调：水彩绿 + 楷体(`'KaiTi','STKaiti','楷体','Kaiti SC'`) + 圆角胶囊按钮；浅色主题。

## 设计约定（2026-09-14 确立）
- **贴纸风图标规范**：深墨绿描边 `#23541b`/`#2f6b28`，填充用浅绿 `#8fc46a`/`#a9dd8b`、
  奶油 `#fbfdf3`/`#fff8e6`、橙 `#f7a53c`/`#ffd45e`、蓝 `#cfe8fa`；线宽 1.6~2。
  参考素材在 `frontend/UI优化讨论*.png`。
- 图标容器统一 `<span class="z-ico ico-xxx"><svg viewBox="0 0 48 48">`（按钮内 29×29，`vertical-align:-7px`）。
- 主操作按钮橙色（`linear-gradient(180deg,#ffe6a8,#ffd17a,#ffbe5c)` + 边框 `#f0a04a`），
  主文字深绿 `#1e4d18`；次要按钮奶白/浅绿胶囊。
- 弹窗统一用**奶油渐变圆角卡**（`.xxx-sheet`），带径向圆点装饰，不要白色方卡。

## 操作准则
- 改前端前先备份（已有 `index.html.bak-*` 习惯）。
- 用 `agent-browser` 截图自查。**注意：直连会挂起**，必须
  `timeout 150 agent-browser open "<url>" --timeout 20000`（外层 timeout + `--timeout` 都要给）。
  常用：`agent-browser click <sel>` / `agent-browser eval "<js>"` / `agent-browser screenshot <path>.png`。
- 临时预览脚本用 `_tmp_` 前缀命名，核对完立即删除。

## 前端约定（补充）
- **API 访问一律用 `apiFetch(path, options)`**（不要再用 `fetch(\`${API_BASE}…\`)`）。
  它按 `API_CANDIDATES` 依次尝试：8000 同源 → 其它端口回退 `http://localhost:8000`，
  网络层失败自动换下一个候选。这样 8080 / file:// / 8000 三种打开方式都能连上后端。
- 后端**同时托管前端**：`http://localhost:8000` 即可前后端一体（推荐入口）。
  `run_frontend.bat` 另开 8080 静态服务器是旧习惯，需两边都启动。
- **含空格/中文的静态资源路径**（如 `生成可爱动态图 (2).mp4`）：文件名带**空格**的必须写 URL 编码
  `%20` 形式；**无空格的中文名**（如 `生成可爱动态图.mp4`）可直接写原名。
  两个 `<video>` 都已加 `onerror="retryVideoSource(this)"` + `data-alt-src`/`data-encoded-src`
  自动在「编码 / 未编码」两种写法间重试一次，正常无需手改。
- **不再使用任何 `<video>`**：右上角 `#profileFab` 与「一句话开局」按钮的 `.pill-video`
  现在都是静态 `<img src="cat.webp">`（用户明确"视频显示失败，换成图片，不用视频了"）。
  对应的 `.fab-video` / `.pill-video` 类名保留，但内部元素是 `img` 而非 `video`。
- 动图分工（历史记录）：`生成可爱动态图 (2).mp4` 曾用于 `#profileFab`，
  `生成可爱动态图.mp4` 曾用于「一句话开局」—— 现已改为 `cat.webp`。
- 开始页（`#startModal`）**不允许出现滚动条**：内容要一屏放下（`.modal-content` 需
  `max-height:none; overflow:visible`，并压缩留白）。logo 宽 400px、标题 25px 是实测能放下的值。
- **游戏界面字号改动必须用 `#gameScreen` 作用域**覆盖，否则会污染开始页（一屏放下会被破坏）
  与弹窗。推理历史气泡的类名是 `.chat-row`/`.chat-bubble`/`.chat-avatar`（**没有** `.inquiry-*`）。
- 学习模式入口是**弹窗** `#learningDialog`，只有材料、**没有学科**；材料存 `learningMaterialText`，
  `startGame()` 只发 `learning_content`。
- 个人资料入口是右上角 **68px 圆形头像** `#profileFab`（无 Lv 徽章、无文字）。
- **游戏页顶栏「推理等级」以个人资料为准**：`GameState.ability.reasoning_level`
  默认是 1，必须在 `GameController.__init__`（start）和 `from_save`（resume）
  里从 `load_profile()["level"]` 覆盖，否则游戏页恒显示 Lv.1（而首页是 Lv.N）。
- **刷新后要停在原界面**：用 `sessionStorage['hs_screen']`（`setScreen/getScreen`）。
  界面切换只走 `showGameScreen()` / `showStartScreen()` 两个入口，别直接操作 classList；
  页面加载用 `initPageState()`（`await checkResume()` 后按标记决定是否 `resumeGame()`）。
  「再来一局」走 `restartToHome()`（不是 `location.reload()`，否则会又被拉回游戏页）。
- **AI 回复不要空行**：`.chat-bubble` 是 `pre-wrap` + `textContent` 写入，
  AI 输出的 `\n\n` 会原样渲染成大段空白。已用 `collapseBlankLines()`
  （`\n{2,}` → `\n`，并去首尾空行）在**渲染层**压平，接入两处：
  ① `addInquiryToHistory()` ② `addTypingBubble()` 的 `render()`（流式路径也要，否则打字时先撑出空白）。
  ⚠️ 新增任何把 AI 文本写进气泡的地方，都要过这个函数。
- **不做 AI 模型选择 UI**（用户 2026-09-14 明确否决，已完整回滚）。
  想换模型只改 `.env` 的 `LLM_MODEL` 即可 —— 网关支持 `claude-opus-5`/`gpt-5.5`/
  `gemini-3.1-pro-preview`/`kimi-k3`/`grok-4.6` 等（详见当日日志第 21 条）。

## 后端约定（backend/）
- **解释器**：项目用 `D:\develop\anaconda\python.exe`（见 `run_backend.bat`）。
  系统默认 `python` 缺 `requests` 等依赖，跑代码/测试务必用 anaconda 那个。
- **启动**：`backend/` 目录下 `main.py`，监听 0.0.0.0:8000。改完代码需**重启后端**才生效。
- **静态资源不再用 `StaticFiles`**：改用文件末尾的自定义兜底路由
  `@app.get("/{full_path:path}")` → `_serve_frontend()`（`unquote` → 防穿越 →
  `FileResponse`（自带 Range）→ NFC 规范化模糊匹配）。原 `StaticFiles` 对
  「中文+空格+括号」文件名会 400/404，是「图形显示失败」的根因。
  ⚠️ 该路由**必须定义在所有 `@app.xxx` API 路由之后**，否则会吞掉 `/api/*`。
- **验证后端务必用 in-process uvicorn**（`uvicorn.Server` + 线程），
  因为**沙箱会在命令结束时回收所有子进程**，`nohup`/`Start-Process` 都留不住。
- **本机有代理** `http_proxy=http://127.0.0.1:60947`：curl 访问本地要加 `--noproxy '*'`；
  `curl --path-as-is` 用于含空格/中文的路径（否则 curl 自身报 400）。
- **上传解析**：`/api/learning/upload` 支持 PDF / Word(docx) / txt / md。
  docx 用**纯标准库** `_extract_docx_text()`（zipfile + re 读 `word/document.xml`），
  **不依赖 python-docx**（环境里没装）。旧版 `.doc` 明确不支持，提示另存为 docx。
- **流式协议**：`process_inquiry_stream` 是异步生成器，yield `("delta", 文本)` / `("final", payload)`；
  **payload 是 `(ai_response, state_updates)` 元组**，不是 dict。所有 `_finalize_*` 都要兼容这点
  （`ai_response, state_updates = payload`）。新增 finalize 函数务必照此解包，否则报
  `'tuple' object has no attribute 'get'`。
- **破案结算**：`completeness > 60` = 成功（升 1 级）；`> 80` = 优秀（升 2 级）。
  等级存 `backend/data/player_profile.json`。
- **等级决定开局资源**（`player_profile.py`，用户 2026-09-14 定稿）：
  - 线索数 `clue_count_for_level(lv)` = `3 + (lv-1)` → Lv1=3, Lv2=4 … Lv5=7
  - 推理次数 `turns_for_level(lv)` = `11 + (lv-1)*2` → Lv1=11, Lv2=13, Lv3=15
  - 接线在 `game_controller.start_new_game`；`clue_count` 贯穿 `case_generator`
    的 4 个方法 + 视角层缓存 key；`_fit_clue_count()` 负责把 LLM 产出对齐到目标条数
    （多了截断且**优先保留 critical**，少了补通用线索，并补 `perspective`）。
    ⚠️ 娱乐模式 prompt 原本没有 `perspective` 字段，改动时必须一并加。
- **推理进度 = 已找到线索 / 总线索**：`GameState.sync_progress_with_clues()`
  （`revealed*100/(revealed+hidden)`）。`reveal_clue()` 会自动调用；
  `update_progress(delta)` **不再累加** delta（只用于卡住判定）。
  任何直接 `case.revealed_clues.append()` 的地方都要补一次 sync。
- **游戏页顶栏有「返回」按钮**（`.top-bar-left` + `.back-btn` → `backToHome()`）：
  回首页但**保留存档**，可从个人资料「继续上局」回来。
- **「🧠 推理能力」面板已删除**（用户认为没用），别再恢复。
- **学习挑战**：答对后随机抽增益（insight/logic/knowledge/association/extra_turn/hidden_clue）。
- **接口约定**（易踩坑）：
  - `/api/game/start` body：`{mode: "entertainment"|"learning", identity, ...}`；
    案件在 **`data.game_state.case`**，不在 `data.case`。`truth` 字段服务端不下发（空 dict）。
  - `/api/game/action/stream` body：`{game_id, action_type, content}`；
    `action_type` ∈ question / hypothesis / **verification** / hint / ask_person / learning / identity_action。
  - SSE 帧是 `data: {...}` 单行 JSON，含 `type`：`delta`(text) / `final`(data) / `error`(message) / `status`。
    解析不能只读前几行——`final` 那行很长，要读完。

## 已验证结论（2026-09-14 端到端）
- 重启后端后（旧实例占 8000 会导致改动不生效，需先杀进程）实测：
  - 提交与真相一致答案 → 还原度 **98%**、`is_excellent=True`、`case_solved=True`、
    结算出现「📖 全部真相」「待解谜团·逐一揭秘」、个人等级 `Lv.1 → Lv.3（+2）`。
  - 提交错误答案 → 还原度 5%，不崩溃，给出命中/未命中/遗漏分析。
  - 60 次学习增益抽样：6 种类型均匀出现。
  - `'tuple' object has no attribute 'get'` 已根除（日志无 Traceback）。
- 存档 `backend/data/game_save.json` 含完整 `case.truth`，可用于构造高还原度回归测试。

