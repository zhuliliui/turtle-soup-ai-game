# 海龟汤推理游戏 - 快速启动指南

## 编码问题说明

如果 `run_backend.bat` 出现中文乱码，请使用以下英文版脚本。

## 启动方式

### 方式1：一键启动（英文版）
双击运行：`run_backend.bat`

### 方式2：分步启动

1. 安装依赖（首次运行）
   ```
   双击 run_backend.bat
   ```

2. 启动后端
   ```
   双击 run_backend.bat
   ```

3. 启动前端（新开一个终端）
   ```
   双击 run_backend.bat
   ```

4. 打开浏览器
   ```
   访问 http://localhost:8080
   ```

### 方式3：命令行启动

打开 CMD，执行：

```cmd
# 1. 安装依赖（首次）
cd backend
pip install -r requirements.txt

# 2. 启动后端
python main.py
```

新开一个 CMD：
```cmd
# 3. 启动前端
cd frontend
python -m http.server 8080
```

## 验证启动成功

后端启动后会看到：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

前端启动后会看到：
```
Serving HTTP on 0.0.0.0 port 8080
```

## 访问地址

- 在线试玩（固定链接）: https://15cd6151e0904833885706cd26a4793c.app.workbuddy.host
- 本地游戏界面: 运行 run_backend.bat 后打开 http://localhost:8000
- API文档: http://localhost:8000/docs

## 故障排查

### 端口被占用
如果看到 `Address already in use` 错误：

```cmd
# 查看占用端口的进程
netstat -ano | findstr :8000
netstat -ano | findstr :8080

# 结束进程（将PID替换为实际进程ID）
taskkill /PID <进程ID> /F
```

### 依赖安装失败
```cmd
# 升级pip
python -m pip install --upgrade pip

# 重新安装
cd backend
pip install -r requirements.txt --no-cache-dir
```

### Python版本问题
确保使用 Python 3.9+：
```cmd
python --version
```

### API Key未配置
检查 `backend\.env` 文件，确保：
```
ANTHROPIC_API_KEY=sk-ant-你的密钥
```

## 测试API

在浏览器打开：http://localhost:8000/docs

会看到FastAPI自动生成的交互式文档。

点击 `GET /` 测试接口是否正常。

## 常见错误

**错误**: `ModuleNotFoundError: No module named 'fastapi'`
**解决**: 运行 `run_backend.bat` 安装依赖

**错误**: `Error: ANTHROPIC_API_KEY not found`
**解决**: 配置 `backend\.env` 文件

**错误**: 浏览器打开后显示 404
**解决**: 确保访问的是 http://localhost:8080 而不是 8000

## 成功启动的标志

1. 后端窗口显示 "Application startup complete"
2. 前端窗口显示 "Serving HTTP on"
3. 浏览器能打开游戏界面
4. 点击"开始游戏"能看到案件生成

现在开始游戏吧！
