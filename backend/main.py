"""FastAPI后端API"""
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from enum import Enum
from dotenv import load_dotenv
import os
import json
import asyncio

# 前端静态目录（backend/ 的上一级 frontend/）
_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

# 加载环境变量
load_dotenv()
_api_key = os.getenv('ANTHROPIC_API_KEY') or ''
print(f"[启动] API_BASE_URL = {os.getenv('API_BASE_URL')}")
print(f"[启动] ANTHROPIC_API_KEY 已配置（{_api_key[:6]}****，长度{len(_api_key)}）" if _api_key else "[启动] ANTHROPIC_API_KEY 未配置！")

from game_engine.game_controller import GameController, SAVE_PATH
from ai_host.llm_client import get_llm_client
from models.game_state import GameMode
from player_profile import load_profile
from zhihu_integration import router as zhihu_router

app = FastAPI(title="海龟汤推理游戏 API")

# 知乎黑客松集成：OAuth 登录 + 知乎故事改编（zhihu_integration.py）
app.include_router(zhihu_router)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 游戏控制器实例（生产环境应该用数据库存储状态）
game_controllers = {}


@app.get("/api/profile")
async def get_profile():
    """玩家个人资料：等级、胜负统计、完成的案件记录（最新在前）"""
    profile = load_profile()
    total = profile["wins"] + profile["losses"]
    return {
        "level": profile["level"],
        "wins": profile["wins"],
        "losses": profile["losses"],
        "total": total,
        "win_rate": round(profile["wins"] * 100.0 / total, 1) if total else 0.0,
        "records": list(reversed(profile["records"]))
    }


class GameModeEnum(str, Enum):
    entertainment = "entertainment"
    learning = "learning"


class StartGameRequest(BaseModel):
    identity: str = ""
    mode: GameModeEnum = GameModeEnum.entertainment
    learning_content: Optional[str] = None
    subject: Optional[str] = None
    premise: Optional[str] = None  # 一句话开局：如"小明昨晚失踪了。我是他的老师"


class PlayerActionRequest(BaseModel):
    game_id: str
    action_type: str  # question, hypothesis, verification, hint, learning
    content: str


class ExerciseAnswerRequest(BaseModel):
    game_id: str
    answer: str


@app.get("/")
async def root():
    """根路径：优先返回前端页面（单端口部署，公网 Demo 同源访问），否则返回 API 信息"""
    index_path = os.path.join(_FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"message": "海龟汤推理游戏 API", "status": "running"}


@app.post("/api/game/start")
async def start_game(request: StartGameRequest):
    """开始新游戏"""
    try:
        llm_client = get_llm_client()
        controller = GameController(llm_client)

        mode = GameMode.ENTERTAINMENT if request.mode == GameModeEnum.entertainment else GameMode.LEARNING

        result = await controller.start_new_game(
            identity=request.identity,
            mode=mode,
            learning_content=request.learning_content,
            subject=request.subject,
            premise=request.premise
        )

        game_id = result["game_id"]
        game_controllers[game_id] = controller

        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _check_result(result: Dict) -> Dict:
    """统一处理控制器返回结果：含error字段的视为业务失败，前端据此提示"""
    if isinstance(result, dict) and result.get("error"):
        return {"success": False, "error": result["error"]}
    return {"success": True, "data": result}


@app.post("/api/game/action")
async def player_action(request: PlayerActionRequest):
    """处理玩家行动"""
    controller = game_controllers.get(request.game_id)
    if not controller:
        raise HTTPException(status_code=404, detail="游戏不存在或已失效，请重新开始游戏")

    try:
        result = await controller.handle_player_action(
            action_type=request.action_type,
            content=request.content
        )
        return _check_result(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no"
}


def _sse(data: Dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/game/action/stream")
async def player_action_stream(request: PlayerActionRequest):
    """流式处理玩家行动（SSE：delta增量 → final结果 / error错误）"""
    controller = game_controllers.get(request.game_id)
    if not controller:
        raise HTTPException(status_code=404, detail="游戏不存在或已失效，请重新开始游戏")

    async def event_gen():
        try:
            async for event in controller.handle_player_action_stream(
                action_type=request.action_type,
                content=request.content
            ):
                yield _sse(event)
        except Exception as e:
            yield _sse({"type": "error", "message": f"服务器错误：{e}"})

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.post("/api/game/start/stream")
async def start_game_stream(request: StartGameRequest):
    """流式开始新游戏（SSE：status进度 → final结果 / error错误）"""
    llm_client = get_llm_client()
    controller = GameController(llm_client)
    mode = GameMode.ENTERTAINMENT if request.mode == GameModeEnum.entertainment else GameMode.LEARNING

    q: asyncio.Queue = asyncio.Queue()

    async def on_status(text: str):
        await q.put({"type": "status", "text": text})

    async def run():
        try:
            result = await controller.start_new_game(
                identity=request.identity,
                mode=mode,
                learning_content=request.learning_content,
                subject=request.subject,
                premise=request.premise,
                on_status=on_status
            )
            await q.put({"type": "final", "data": result})
        except Exception as e:
            await q.put({"type": "error", "message": str(e)})

    task = asyncio.create_task(run())

    async def event_gen():
        final_result = None
        while True:
            event = await q.get()
            if event["type"] in ("final", "error"):
                if event["type"] == "final":
                    final_result = event["data"]
                    game_controllers[final_result["game_id"]] = controller
                yield _sse(event)
                break
            yield _sse(event)

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.get("/api/game/resume")
async def resume_game():
    """恢复上局存档（后端重启后可继续玩）"""
    try:
        if not os.path.exists(SAVE_PATH):
            return {"success": True, "has_save": False}

        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 已结束的存档无需恢复
        if data.get("game_over"):
            return {"success": True, "has_save": False}

        controller = GameController.from_save(data, get_llm_client())
        if not controller or not controller.game_state:
            return {"success": True, "has_save": False}

        game_controllers[controller.game_state.game_id] = controller

        gs = controller.game_state
        welcome = controller.host.greet_player(gs.user_identity, gs.mode.value)
        case_presentation = controller.host.present_case(
            gs.case.title, gs.case.background, gs.case.scene_description
        )
        return {
            "success": True,
            "has_save": True,
            "data": {
                "game_id": gs.game_id,
                "welcome_message": welcome,
                "case_presentation": case_presentation,
                "user_identity": gs.user_identity,
                "resumed": True,
                "game_state": controller._serialize_game_state()
            }
        }
    except Exception as e:
        return {"success": True, "has_save": False, "error": str(e)}


@app.post("/api/game/exercise/submit")
async def submit_exercise(request: ExerciseAnswerRequest):
    """提交习题答案"""
    controller = game_controllers.get(request.game_id)
    if not controller:
        raise HTTPException(status_code=404, detail="游戏不存在或已失效，请重新开始游戏")

    try:
        result = await controller.submit_exercise_answer(request.answer)
        return _check_result(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/game/{game_id}/state")
async def get_game_state(game_id: str):
    """获取游戏状态"""
    controller = game_controllers.get(game_id)
    if not controller:
        raise HTTPException(status_code=404, detail="游戏不存在")

    return {"success": True, "data": controller._serialize_game_state()}


@app.post("/api/learning/upload")
async def upload_learning_material(file: UploadFile = File(...)):
    """上传学习材料（支持 PDF / 纯文本），返回提取的文本内容"""
    try:
        content = await file.read()
        filename = file.filename or ""

        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件太大（超过20MB）")

        if filename.lower().endswith(".pdf") or content[:5] == b"%PDF-":
            text = _extract_pdf_text(content)
            if text is None:
                raise HTTPException(status_code=400, detail="PDF解析失败：文件可能已损坏，或是扫描版PDF（无文字层）。请改用粘贴文字")
        else:
            # 纯文本类（txt/md等），宽松解码
            text = content.decode("utf-8", errors="replace")

        text = text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="没有从文件中提取到文字内容")

        # 截断过长内容，避免LLM上下文爆炸
        truncated = False
        if len(text) > 20000:
            text = text[:20000]
            truncated = True

        return {
            "filename": filename,
            "text": text,
            "chars": len(text),
            "truncated": truncated
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")


def _extract_pdf_text(data: bytes) -> Optional[str]:
    """用 PyPDF2 提取PDF文字（anaconda 自带 PyPDF2，无需额外安装）"""
    try:
        import io
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = []
        # 最多取前60页，防止超长文档卡死
        for page in reader.pages[:60]:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        return "\n".join(pages)
    except Exception as e:
        print(f"[上传] PDF解析失败: {e}")
        return None


@app.delete("/api/game/{game_id}")
async def end_game(game_id: str):
    """结束游戏，释放资源"""
    if game_id in game_controllers:
        del game_controllers[game_id]
        return {"success": True, "message": "游戏已结束"}
    else:
        raise HTTPException(status_code=404, detail="游戏不存在")


# 前端静态资源挂载（bg.jpg / sw.js 等；必须在所有 API 路由之后，避免覆盖 /api/*）
if os.path.isdir(_FRONTEND_DIR):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
