# 海龟汤推理游戏 - AI Agent

一个融合**推理解谜**和**学习成长**的双模式AI游戏。

> 🌐 **在线试玩（固定链接）**：https://15cd6151e0904833885706cd26a4793c.app.workbuddy.host
> 💻 本地运行：双击 `run_backend.bat`，浏览器打开 http://localhost:8000

## 🎮 核心特色

### 双模式体验

**娱乐模式**
- 根据你的身份（侦探/医生/记者等）生成定制海龟汤案件
- 10轮推理机会破解案件
- AI主持人带来游戏感，而非聊天机器人感

**学习模式**
- 上传学习材料，AI生成知识点和习题
- 答题正确获得推理增益（额外轮次、隐藏线索、能力提升）
- 案件与学习内容关联，寓学于乐

### 核心系统

**推理成长系统**
- 观察力、逻辑力、联想力、知识力四维能力
- 推理进度实时反馈
- 推理增益系统

**智能AI主持人**
- 不是简单回答"是/否"，而是带有引导性的反馈
- 动态揭示线索
- 检测卡住状态，主动提供帮助

**学习挑战系统**
- 自动提取知识点
- 生成单选、判断、简答题
- AI自动评分简答题
- 学习成果转化为游戏增益

## 🏗️ 技术架构

### 后端
- **FastAPI** - 高性能API框架
- **Claude API** - 案件生成、推理判断、习题生成
- **Python 3.9+** - 核心逻辑

### 前端
- **原生HTML/CSS/JS** - 游戏风格界面
- 非传统聊天窗口，而是游戏面板布局

### 核心模块
```
backend/
├── models/          # 数据模型
│   └── game_state.py
├── ai_host/         # AI主持人
│   ├── host_persona.py      # 主持人人格
│   ├── reasoning_engine.py  # 推理判断引擎
│   └── llm_client.py        # LLM客户端
├── game_engine/     # 游戏引擎
│   ├── case_generator.py    # 案件生成
│   └── game_controller.py   # 游戏控制器
├── learning/        # 学习系统
│   └── learning_system.py   # 知识提取、习题生成、评分
└── main.py          # API入口
```

## 🚀 快速开始

### 1. 环境配置

```bash
# 安装依赖
cd backend
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 Anthropic API Key
```

### 2. 启动后端

```bash
cd backend
python main.py
```

后端将在 `http://localhost:8000` 启动

### 3. 启动前端

直接用浏览器打开 `frontend/index.html`

或者使用简单的HTTP服务器：
```bash
cd frontend
python -m http.server 8080
```

然后访问 `http://localhost:8080`

## 🎯 游戏玩法

### 娱乐模式

1. **输入身份** - 选择你的角色（侦探、医生、学生等）
2. **AI生成案件** - 根据你的身份生成定制海龟汤
3. **开始推理** - 10轮机会，通过提问和推理破案
4. **还原真相** - 揭示完整真相，查看推理报告

### 学习模式

1. **上传学习材料** - 粘贴课本内容、知识点
2. **AI生成案件** - 案件主题关联学习内容
3. **推理+学习** - 遇到困难时完成学习挑战
4. **获得增益** - 答题正确获得推理能力提升
5. **破案成功** - 既掌握知识，又破解案件

### 操作说明

**提问** - 向AI主持人提出问题
- 触及关键点会获得更多信息
- AI会给出引导性反馈

**提出猜想** - 表达你的推理
- AI评估准确度并给出反馈
- 帮助你调整推理方向

**还原真相** - 完整还原案件真相
- 需要说明：谁、什么、为什么、怎么做
- 正确则破案，错误则继续推理

**请求提示** - 消耗推理机会获取提示
- 当你卡住时使用
- AI会引导你关注被忽略的线索

**学习挑战**（仅学习模式）
- 完成习题获得增益
- 单选/判断自动判分
- 简答题AI评分

## 📊 推理系统

### 能力值
- **观察力** - 发现细节的能力
- **逻辑力** - 推理判断的能力
- **联想力** - 关联信息的能力
- **知识力** - 运用知识的能力

### 推理增益
答题正确可获得：
- 🔍 **洞察** - 下次提问获得额外信息
- 🧩 **逻辑** - 推理判断更准确
- 📖 **知识** - 获得案件相关知识提示
- ⏳ **推理机会+1** - 增加提问次数
- 🎁 **隐藏线索** - 解锁关键线索

## 🛠️ API文档

### 开始游戏
```
POST /api/game/start
{
  "identity": "侦探",
  "mode": "entertainment",  // or "learning"
  "learning_content": "...",  // 学习模式必需
  "subject": "生物"  // 可选
}
```

### 玩家行动
```
POST /api/game/action
{
  "game_id": "...",
  "action_type": "question",  // question/hypothesis/verification/hint
  "content": "死者认识凶手吗？"
}
```

### 提交习题答案
```
POST /api/game/exercise/submit
{
  "game_id": "...",
  "answer": "A"
}
```

### 获取游戏状态
```
GET /api/game/{game_id}/state
```

## 🎨 界面设计

区别于传统聊天界面：

**顶部状态栏**
- 案件标题
- 剩余推理次数
- 推理进度条
- 推理等级

**中央案件面板**
- 案件背景和现场描述
- 已知线索（关键线索高亮）
- 推理对话历史
- 底部操作按钮

**右侧推理面板**
- 推理能力显示
- 当前增益列表
- 待解谜团

## 🔧 配置说明

### 环境变量 (.env)

```env
# Anthropic API Key（必需）
ANTHROPIC_API_KEY=sk-ant-xxx

# LLM模型
LLM_MODEL=claude-sonnet-4-5-20250929

# 服务器配置
HOST=0.0.0.0
PORT=8000
```

## 📝 开发说明

### 扩展案件模板

编辑 `backend/game_engine/case_generator.py` 中的 `CaseTemplates` 类

### 调整AI人格

编辑 `backend/ai_host/host_persona.py` 中的对话模板

### 修改推理规则

编辑 `backend/ai_host/reasoning_engine.py` 中的判断逻辑

## 🐛 常见问题

**Q: API调用失败？**
A: 检查 `.env` 文件中的 `ANTHROPIC_API_KEY` 是否正确

**Q: 前端无法连接后端？**
A: 确保后端已启动在 `http://localhost:8000`，检查CORS配置

**Q: 案件生成很慢？**
A: Claude API调用需要时间，特别是生成复杂案件时，请耐心等待

**Q: 学习模式习题不准确？**
A: 可以调整 `learning_system.py` 中的提示词来优化习题质量

## 🚀 未来扩展

- [ ] 案件难度选择
- [ ] 多人协作推理模式
- [ ] 推理成就系统
- [ ] 历史案件回顾
- [ ] 自定义案件编辑器
- [ ] 语音交互
- [ ] 移动端适配

## 📄 许可证

MIT License

## 🙏 致谢

- Claude API - AI能力支持
- FastAPI - 高性能API框架

---

**开始你的推理之旅吧！** 🕵️‍♂️🧩
