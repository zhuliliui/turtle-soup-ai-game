"""LLM客户端封装 - 支持Claude API"""
from typing import Optional, Dict, AsyncGenerator
import os
import asyncio
import threading
import queue as _queue
import requests
import json
import re


class LLMError(Exception):
    """LLM调用失败异常 - 让上层能够感知失败并做出正确处理（如不消耗推理机会）"""
    pass


class LLMClient:
    """LLM客户端 - 封装对Claude API的调用"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929")

        if not self.api_key:
            raise LLMError("未配置 ANTHROPIC_API_KEY，请检查 backend/.env 文件")

        # 支持自定义API网关
        self.base_url = os.getenv("API_BASE_URL", "https://api.anthropic.com").rstrip("/")
        print(f"[LLM] 使用API端点: {self.base_url}, 模型: {self.model}")

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        retries: int = 1
    ) -> str:
        """
        生成文本（异步不阻塞事件循环）

        失败时抛出 LLMError，由上层决定如何兜底。

        Args:
            prompt: 用户提示词
            max_tokens: 最大token数
            temperature: 温度参数（0-1）
            system_prompt: 系统提示词
            retries: 失败后的重试次数

        Returns:
            生成的文本

        Raises:
            LLMError: API调用失败
        """

        url = f"{self.base_url}/v1/messages"
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

        data = {
            'model': self.model,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'messages': [{'role': 'user', 'content': prompt}]
        }

        if system_prompt:
            data['system'] = system_prompt

        last_error = None
        for attempt in range(1 + retries):
            try:
                # requests是同步库，放到线程池执行，避免阻塞FastAPI事件循环
                response = await asyncio.to_thread(
                    requests.post, url, headers=headers, json=data, timeout=120
                )

                if response.status_code != 200:
                    error_msg = f"API返回错误 {response.status_code}: {response.text[:200]}"
                    print(f"[LLM] {error_msg}")
                    # 4xx客户端错误（key无效等）重试也没用，直接抛出
                    if 400 <= response.status_code < 500:
                        raise LLMError(error_msg)
                    last_error = LLMError(error_msg)
                    continue

                # 防御：响应头缺 charset 时 requests 有 latin-1 回退隐患，显式按 UTF-8 解码
                response.encoding = "utf-8"
                result_json = response.json()
                content_blocks = result_json.get('content') or []
                texts = [b.get('text', '') for b in content_blocks if isinstance(b, dict) and b.get('type') == 'text']
                result = ''.join(texts).strip()

                if not result:
                    last_error = LLMError("API返回了空内容")
                    print(f"[LLM] {last_error}")
                    continue

                print(f"[LLM] API 调用成功, 返回长度: {len(result)}")
                return result

            except LLMError:
                raise
            except Exception as e:
                last_error = LLMError(f"API调用失败: {type(e).__name__}: {e}")
                print(f"[LLM] {last_error} (第{attempt + 1}次尝试)")
                continue

        raise last_error or LLMError("API调用失败")

    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成：逐段 yield 文本增量（Anthropic SSE 协议）

        后台线程负责读 HTTP 流并写入队列，异步侧逐条取用，
        避免阻塞 FastAPI 事件循环。失败抛 LLMError。
        """
        url = f"{self.base_url}/v1/messages"
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

        data = {
            'model': self.model,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'stream': True,
            'messages': [{'role': 'user', 'content': prompt}]
        }

        if system_prompt:
            data['system'] = system_prompt

        loop = asyncio.get_running_loop()
        q: "_queue.Queue" = _queue.Queue()

        def _worker():
            try:
                resp = requests.post(url, headers=headers, json=data, timeout=180, stream=True)
                if resp.status_code != 200:
                    q.put(LLMError(f"API返回错误 {resp.status_code}: {resp.text[:200]}"))
                    return

                got_any = False
                # 注意：decode_unicode=True 在响应头无 charset 时会按 Latin-1 解码，
                # 导致中文变乱码（requests 的 RFC 默认行为）。改为手动按 UTF-8 解码。
                for raw in resp.iter_lines(decode_unicode=False):
                    if not raw:
                        continue
                    if isinstance(raw, bytes):
                        line = raw.decode("utf-8", errors="replace").strip()
                    else:
                        line = str(raw).strip()
                    if line.startswith("event:"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    payload = line.split(":", 1)[1].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    ev_type = obj.get("type", "")
                    if ev_type == "content_block_delta":
                        delta = obj.get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            got_any = True
                            q.put(("delta", delta["text"]))
                    elif ev_type == "message_stop":
                        break
                    elif ev_type == "error":
                        msg = (obj.get("error") or {}).get("message", "unknown")
                        q.put(LLMError(f"API流式错误: {msg}"))
                        return

                if not got_any:
                    q.put(LLMError("API流式返回了空内容"))
                    return
                q.put(None)  # 正常结束哨兵
            except LLMError as e:
                q.put(e)
            except Exception as e:
                q.put(LLMError(f"API流式调用失败: {type(e).__name__}: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

        while True:
            item = await loop.run_in_executor(None, q.get)
            if item is None:
                break
            if isinstance(item, LLMError):
                raise item
            yield item[1]

    async def generate_json(
        self,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.2
    ) -> Dict:
        """
        生成JSON格式响应

        适用于需要结构化输出的场景

        Raises:
            LLMError: API调用失败或无法解析出JSON
        """

        json_prompt = f"{prompt}\n\n请严格按照JSON格式返回，不要包含其他说明文字。"
        response_text = await self.generate(
            json_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

        parsed = extract_json(response_text)
        if parsed is None:
            raise LLMError("无法从AI回复中解析出JSON")
        return parsed


def extract_json(response: str) -> Optional[Dict]:
    """
    从LLM响应中提取JSON对象（统一工具函数）

    支持 ```json ... ``` 代码块、普通文本夹杂JSON、以及常见JSON格式错误修复。
    解析失败返回 None（而不是静默返回 {}，便于上层区分"解析失败"和"空对象"）。
    """
    if not response:
        return None

    # 1. 优先提取 ```json ... ``` 包裹的内容
    fence_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response, re.DOTALL)
    candidates = []
    if fence_match:
        candidates.append(fence_match.group(1))

    # 2. 整个响应中最外层的 {...}
    brace_match = re.search(r'\{.*\}', response, re.DOTALL)
    if brace_match:
        candidates.append(brace_match.group())

    for json_str in candidates:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # 尝试修复常见错误：尾随逗号
        fixed = re.sub(r',\s*([}\]])', r'\1', json_str)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            continue

    return None


# 单例模式
_llm_client_instance = None


def get_llm_client() -> LLMClient:
    """获取LLM客户端单例"""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance
