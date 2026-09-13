"""项目使用指南"""

# 海龟汤推理游戏 - 快速上手

## 第一步：配置API Key

1. 打开 `backend/.env.example`
2. 复制为 `backend/.env`
3. 填入你的 Anthropic API Key：

```
ANTHROPIC_API_KEY=sk-ant-你的key
```

获取API Key: https://console.anthropic.com/

## 第二步：安装依赖

```bash
cd backend
pip install -r requirements.txt
```

依赖包括：
- fastapi - Web框架
- uvicorn - ASGI服务器
- anthropic - Claude API客户端
- pydantic - 数据验证

## 第三步：启动服务

### Windows用户
双击 `start.bat`

### Mac/Linux用户
```bash
./start.sh
```

### 手动启动
```bash
# 终端1：启动后端
cd backend
python main.py

# 终端2：启动前端
cd frontend
python -m http.server 8080
```

## 第四步：开始游戏

浏览器访问: http://localhost:8080

## 游戏流程示例

### 娱乐模式
1. 输入身份："侦探"
2. 选择"娱乐模式"
3. 点击"开始游戏"
4. AI生成案件
5. 开始推理：
   - 提问："死者身上有伤口吗？"
   - AI回答："是的，但没有外伤"
   - 继续提问获取线索
   - 推理进度增加
6. 当有足够线索时，点击"还原真相"
7. 输入完整推理，AI判断正误

### 学习模式
1. 输入身份："学生"
2. 选择"学习模式"
3. 填写学科："生物"
4. 粘贴学习材料：
```
光合作用是植物利用光能，将二氧化碳和水转化为有机物，
并释放氧气的过程...
```
5. 开始游戏
6. AI生成与生物知识相关的案件
7. 推理过程中可点击"学习挑战"
8. 完成习题获得推理增益
9. 使用增益继续破案

## 功能说明

### 提问
- 向AI提出具体问题
- 关键问题会推进进度
- AI给出引导性回答

### 提出猜想
- 表达你的推理思路
- AI评估准确度
- 帮助调整方向

### 还原真相
- 完整描述案件真相
- 包括：谁、什么、为什么、怎么做
- 只有全部正确才算破案

### 请求提示
- 消耗1次推理机会
- 获得方向性提示
- 适合卡住时使用

### 学习挑战（学习模式）
- 答题获得增益：
  - 额外推理机会
  - 隐藏线索
  - 能力提升

## 调试技巧

### 查看后端日志
后端启动后会显示详细日志，包括：
- API调用
- 案件生成过程
- 推理判断逻辑

### 查看API文档
访问: http://localhost:8000/docs
FastAPI自动生成的交互式API文档

### 前端调试
按F12打开浏览器开发者工具
- Console: 查看JavaScript日志
- Network: 查看API请求

## 常见问题

**Q: "服务器连接失败"**
A: 确保后端已启动：`cd backend && python main.py`

**Q: "游戏启动失败"**
A: 检查API Key是否正确配置在 `backend/.env`

**Q: 案件生成慢**
A: Claude API需要时间生成，耐心等待10-30秒

**Q: 前端样式显示异常**
A: 清除浏览器缓存，刷新页面

**Q: 简答题评分不准**
A: 可调整 `learning_system.py` 中的评分提示词

## 自定义配置

### 修改案件难度
编辑 `backend/game_engine/case_generator.py`:
```python
# 增加线索数量
"revealed_clues": [...],  # 添加更多初始线索

# 减少推理轮次
self.game_state.total_turns = 8  # 改为8轮
```

### 调整AI人格
编辑 `backend/ai_host/host_persona.py`:
```python
def respond_to_question(self, ...):
    intros = [
        "你的自定义开场白",
        # ...
    ]
```

### 修改习题类型
编辑 `backend/learning/learning_system.py`:
```python
types_to_generate = [
    ExerciseType.SINGLE_CHOICE,
    # 注释掉不需要的类型
]
```

## 性能优化

### 使用缓存
安装Redis，缓存案件模板：
```python
# 在 case_generator.py 中添加
import redis
cache = redis.Redis(...)
```

### 异步处理
所有LLM调用已使用async/await，确保并发性能

### 减少Token消耗
- 缩短提示词
- 减少上下文长度
- 使用更小的模型（需要权衡质量）

## 扩展开发

### 添加新能力
1. 在 `game_state.py` 添加能力类型
2. 在 `learning_system.py` 添加奖励类型
3. 在前端 `index.html` 显示新能力

### 添加新案件模板
在 `case_generator.py` 的 `CaseTemplates` 类添加：
```python
@staticmethod
def get_xxx_case() -> Dict:
    return {
        "title": "...",
        # ...
    }
```

### 集成数据库
替换 `main.py` 中的字典存储：
```python
# 使用SQLAlchemy或MongoDB
from sqlalchemy import create_engine
# ...
```

## 项目结构

```
海龟汤/
├── backend/                    # 后端
│   ├── models/                 # 数据模型
│   │   └── game_state.py
│   ├── ai_host/                # AI主持人
│   │   ├── host_persona.py     # 人格系统
│   │   ├── reasoning_engine.py # 推理引擎
│   │   └── llm_client.py       # LLM客户端
│   ├── game_engine/            # 游戏引擎
│   │   ├── case_generator.py   # 案件生成
│   │   └── game_controller.py  # 游戏控制
│   ├── learning/               # 学习系统
│   │   └── learning_system.py
│   ├── main.py                 # API入口
│   ├── requirements.txt        # 依赖
│   └── .env                    # 环境变量
├── frontend/                   # 前端
│   └── index.html              # 游戏界面
├── README.md                   # 项目文档
├── GUIDE.md                    # 本文件
├── start.bat                   # Windows启动
└── start.sh                    # Mac/Linux启动
```

## 技术细节

### AI主持人系统
- 基于Claude API
- 动态调整回应风格
- 根据推理进度揭示线索
- 检测卡住状态

### 推理判断引擎
- 实时评估问题质量
- 计算推理进度增量
- 决定线索揭示时机
- 验证真相完整性

### 学习系统
- 自动提取知识点
- 生成多类型习题
- AI评分简答题
- 学习成果转化为游戏增益

## 部署建议

### 本地测试
使用 `start.bat` 或 `start.sh`

### 生产部署
1. 使用Gunicorn + Nginx
2. 配置HTTPS
3. 使用数据库存储游戏状态
4. 添加用户认证
5. 监控API调用量和成本

### Docker部署
创建 `Dockerfile`:
```dockerfile
FROM python:3.9
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
```

## 贡献指南

欢迎提交Issue和PR！

改进方向：
- 更多案件模板
- 更智能的推理判断
- 更好的UI/UX
- 移动端适配
- 多语言支持

---

现在开始你的推理之旅！🕵️‍♂️
