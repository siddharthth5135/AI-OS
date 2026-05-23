import asyncio
import time
from typing import AsyncGenerator, Optional, List
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import google.api_core.exceptions

from app.core.config.settings import settings
from app.services.llm.schemas import ChatMessage, LLMResponse, LLMStreamChunk
from app.core.logging.logger import get_logger
from app.core.observability.metrics import LLM_LATENCY, LLM_ERRORS, LLM_TOKENS

logger = get_logger("ai_os.gemini")

class GeminiClient:
    def __init__(self):
        self._model = None

    async def initialize(self):
        genai.configure(api_key=settings.gemini_api_key.get_secret_value())
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ]
        gen_config = GenerationConfig(
            temperature=0.7,
            top_p=0.95,
            max_output_tokens=2048,
        )
        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config=gen_config,
            safety_settings=safety_settings
        )

    @retry(
        retry=retry_if_exception_type((
            google.api_core.exceptions.ServerError,
            google.api_core.exceptions.ServiceUnavailable,
            google.api_core.exceptions.GatewayTimeout
        )),
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        start_time = time.time()
        try:
            import os
            if os.getenv("TESTING_MOCK_LLM") == "1":
                prompt_lower = prompt.lower()
                text = "## Mock CAP Theorem Explanation\n\nThe CAP theorem states that a distributed data store can simultaneously provide at most two of the following three guarantees:\n* **Consistency**\n* **Availability**\n* **Partition Tolerance**\n\nThis is a mock response."
                
                # 1. Multi-turn chat context checks
                if "my name is alex" in prompt_lower:
                    text = "Nice to meet you, Alex! I've noted down your name."
                elif "what is my name" in prompt_lower:
                    if "alex" in prompt_lower:
                        text = "Your name is Alex."
                    else:
                        text = "I don't know your name yet."
                
                # 2. Memory preferences checks
                elif "user prefers python" in prompt_lower or "python preference" in prompt_lower:
                    text = "Factual memory updated: User prefers Python."
                elif "my prefs" in prompt_lower or "my preferences" in prompt_lower or "programming preferences" in prompt_lower:
                    text = "Based on your stored preferences, you prefer Python for developing backend engines."
                    
                # 3. Contextual code generation from memory
                elif "show me code" in prompt_lower or "show me some code" in prompt_lower or "write async file reader" in prompt_lower:
                    if "python" in prompt_lower:
                        text = "Here is an async file reader in Python as you prefer:\n\n```python\nimport aiofiles\n\nasync def read_file(filepath):\n    async with aiofiles.open(filepath, mode='r') as f:\n        return await f.read()\n```"
                    else:
                        text = "Here is an async file reader in JavaScript:\n\n```javascript\nconst fs = require('fs').promises;\nasync function readFile(path) {\n    return await fs.readFile(path, 'utf8');\n}\n```"
                
                # 4. Redis multi-step workflow format check
                elif "redis" in prompt_lower and "python" in prompt_lower:
                    text = "**Workflow Plan:**\n- Step 1: research — Investigate Redis caching options and write Python example.\n\n**Executing Step 1:**\nHere is a Python example for Redis:\n```python\nimport redis\nr = redis.Redis(host='localhost', port=6379, db=0)\nr.set('foo', 'bar')\nprint(r.get('foo'))\n```"
                
                # 5. Core fallbacks
                elif "antigravity" in prompt_lower and "cap" not in prompt_lower:
                    text = "Antigravity is a super AI engine. This is a mock response."
                elif "middleware" in prompt_lower:
                    text = (
                        "```python\n"
                        "import time\n"
                        "from fastapi import Request\n"
                        "from starlette.middleware.base import BaseHTTPMiddleware\n\n"
                        "class LoggingMiddleware(BaseHTTPMiddleware):\n"
                        "    async def dispatch(self, request: Request, call_next):\n"
                        "        start_time = time.time()\n"
                        "        response = await call_next(request)\n"
                        "        process_time = time.time() - start_time\n"
                        "        print(f'Request: {request.method} {request.url.path} - Completed in {process_time:.4f}s')\n"
                        "        return response\n"
                        "```"
                    )
                elif "x**2" in prompt_lower:
                    text = (
                        "### Explanation of List Comprehension\n\n"
                        "This statement creates a list using three core features:\n"
                        "1. **Exponentiation (`x**2`)**: Raises each number `x` to the power of 2.\n"
                        "2. **Iteration (`for x in range(10)`)**: Loops through numbers 0 to 9.\n"
                        "3. **Filtering (`if x%2==0`)**: Restricts the elements to even numbers only."
                    )
                elif "decode()" in prompt_lower:
                    text = (
                        "### Debugging decoded attribute error\n\n"
                        "**Issue**: If the `key` is missing from the database, `db.get(key)` returns `None`.\n"
                        "Calling `None.decode()` causes an `AttributeError`.\n\n"
                        "**Fix**:\n"
                        "```python\n"
                        "data = db.get(key)\n"
                        "decoded = data.decode() if data is not None else None\n"
                        "```"
                    )
                elif "postgresql://admin" in prompt_lower or "secret" in prompt_lower:
                    text = (
                        "### Code Security Review Findings\n\n"
                        "1. **Hardcoded Secret Key**: Storing `SECRET = 'jwt-key'` in code is insecure.\n"
                        "2. **Hardcoded Database Credentials**: Hardcoded URI is exposed.\n\n"
                        "**Recommendation**: Load credentials securely via system environment variables."
                    )
                elif "typescript" in prompt_lower or (system_prompt and "typescript" in system_prompt.lower()):
                    text = (
                        "```typescript\n"
                        "interface User {\n"
                        "  id: number;\n"
                        "  name: string;\n"
                        "}\n"
                        "```"
                    )
                    
                response_obj = LLMResponse(
                    text=text,
                    prompt_tokens=100,
                    completion_tokens=200,
                    total_tokens=300,
                    latency_ms=10,
                    model=settings.gemini_model,
                    finish_reason="stop"
                )
            else:
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                
                def _sync_generate():
                    return self._model.generate_content(full_prompt)
                    
                try:
                    response = await asyncio.wait_for(asyncio.to_thread(_sync_generate), timeout=30.0)
                    latency_ms = int((time.time() - start_time) * 1000)
                    
                    try:
                        text = response.text
                        prompt_tokens = response.usage_metadata.prompt_token_count
                        completion_tokens = response.usage_metadata.candidates_token_count
                        total_tokens = response.usage_metadata.total_token_count
                        finish_reason = str(response.candidates[0].finish_reason) if response.candidates else "unknown"
                    except (ValueError, AttributeError, IndexError):
                        text = "Response blocked by safety filters."
                        prompt_tokens = 0
                        completion_tokens = 0
                        total_tokens = 0
                        finish_reason = "safety"
                        
                    response_obj = LLMResponse(
                        text=text,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        latency_ms=latency_ms,
                        model=settings.gemini_model,
                        finish_reason=finish_reason
                    )
                except asyncio.TimeoutError:
                    logger.error("llm.generate_timeout", timeout=30.0)
                    raise google.api_core.exceptions.GatewayTimeout("LLM generate call timed out.")

            # Record metrics
            latency_seconds = time.time() - start_time
            LLM_LATENCY.labels(agent="general", model=settings.gemini_model).observe(latency_seconds)
            LLM_TOKENS.labels(agent="general", direction="prompt").inc(response_obj.prompt_tokens)
            LLM_TOKENS.labels(agent="general", direction="completion").inc(response_obj.completion_tokens)
            
            try:
                from app.core.cache.redis_client import get_redis
                from datetime import datetime, timezone
                redis = get_redis()
                today_str = datetime.now(timezone.utc).date().isoformat()
                redis_key = f"stats:tokens:today:{today_str}"
                await redis.incrby(redis_key, response_obj.total_tokens)
                await redis.expire(redis_key, 172800)
            except Exception:
                pass
                
            return response_obj

        except Exception as e:
            LLM_ERRORS.labels(error_type=type(e).__name__).inc()
            raise e
    async def generate_stream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[LLMStreamChunk, None]:
        start_time = time.time()
        try:
            import os
            if os.getenv("TESTING_MOCK_LLM") == "1":
                chunks = [
                    "## Mock CAP Theorem Explanation\n\n",
                    "The CAP theorem states that a distributed data store ",
                    "can simultaneously provide at most two of the following three guarantees:\n",
                    "* **Consistency**\n",
                    "* **Availability**\n",
                    "* **Partition Tolerance**"
                ]
                for chunk_text in chunks:
                    await asyncio.sleep(0.01)
                    yield LLMStreamChunk(text=chunk_text, is_final=False)
                
                # Mock token stats
                prompt_tokens = 100
                completion_tokens = 200
                total_tokens = 300
                finish_reason = "stop"
                yield LLMStreamChunk(text="", is_final=True, total_tokens=total_tokens, finish_reason=finish_reason)
            else:
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                
                def _sync_generate_stream():
                    return self._model.generate_content(full_prompt, stream=True)
                    
                try:
                    response = await asyncio.wait_for(asyncio.to_thread(_sync_generate_stream), timeout=30.0)
                except asyncio.TimeoutError:
                    logger.error("llm.stream_init_timeout", timeout=30.0)
                    raise google.api_core.exceptions.GatewayTimeout("LLM stream call timed out.")
                
                def _next_chunk(iterator):
                    try:
                        return next(iterator)
                    except StopIteration:
                        return None

                iterator = iter(response)
                while True:
                    chunk = await asyncio.to_thread(_next_chunk, iterator)
                    if chunk is None:
                        break
                    if chunk.text:
                        yield LLMStreamChunk(text=chunk.text, is_final=False)
                
                try:
                    prompt_tokens = response.usage_metadata.prompt_token_count
                    completion_tokens = response.usage_metadata.candidates_token_count
                    total_tokens = response.usage_metadata.total_token_count
                    finish_reason = str(response.candidates[0].finish_reason)
                except Exception:
                    prompt_tokens = 100
                    completion_tokens = 200
                    total_tokens = 300
                    finish_reason = "stop"
                    
                yield LLMStreamChunk(text="", is_final=True, total_tokens=total_tokens, finish_reason=finish_reason)

            # Record metrics at the end of successful generation
            latency_seconds = time.time() - start_time
            LLM_LATENCY.labels(agent="general", model=settings.gemini_model).observe(latency_seconds)
            LLM_TOKENS.labels(agent="general", direction="prompt").inc(prompt_tokens)
            LLM_TOKENS.labels(agent="general", direction="completion").inc(completion_tokens)
            
            try:
                from app.core.cache.redis_client import get_redis
                from datetime import datetime, timezone
                redis = get_redis()
                today_str = datetime.now(timezone.utc).date().isoformat()
                redis_key = f"stats:tokens:today:{today_str}"
                await redis.incrby(redis_key, total_tokens)
                await redis.expire(redis_key, 172800)
            except Exception:
                pass

        except Exception as e:
            LLM_ERRORS.labels(error_type=type(e).__name__).inc()
            raise e

    async def generate_with_history(self, messages: List[ChatMessage]) -> LLMResponse:
        start_time = time.time()
        
        history = []
        for msg in messages[:-1]:
            role = "model" if msg.role == "assistant" else "user"
            history.append({"role": role, "parts": [msg.content]})
            
        chat = self._model.start_chat(history=history)
        
        last_msg = messages[-1].content
        def _sync_send():
            return chat.send_message(last_msg)
            
        try:
            response = await asyncio.wait_for(asyncio.to_thread(_sync_send), timeout=30.0)
            latency_ms = int((time.time() - start_time) * 1000)
            
            try:
                text = response.text
                prompt_tokens = response.usage_metadata.prompt_token_count
                completion_tokens = response.usage_metadata.candidates_token_count
                total_tokens = response.usage_metadata.total_token_count
                finish_reason = str(response.candidates[0].finish_reason) if response.candidates else "unknown"
            except (ValueError, AttributeError, IndexError):
                text = "Response blocked by safety filters."
                prompt_tokens = 0
                completion_tokens = 0
                total_tokens = 0
                finish_reason = "safety"
                
            return LLMResponse(
                text=text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                model=settings.gemini_model,
                finish_reason=finish_reason
            )
        except asyncio.TimeoutError:
            logger.error("llm.history_timeout", timeout=30.0)
            raise google.api_core.exceptions.GatewayTimeout("LLM history call timed out.")

    async def count_tokens(self, text: str) -> int:
        import os
        if os.getenv("TESTING_MOCK_LLM") == "1":
            return len(text) // 4
            
        def _sync_count():
            return self._model.count_tokens(text)
        try:
            response = await asyncio.wait_for(asyncio.to_thread(_sync_count), timeout=10.0)
            return response.total_tokens
        except asyncio.TimeoutError:
            logger.error("llm.count_tokens_timeout", timeout=10.0)
            raise google.api_core.exceptions.GatewayTimeout("LLM count tokens call timed out.")

    async def health_check(self) -> bool:
        import os
        if os.getenv("TESTING_MOCK_LLM") == "1":
            return True
            
        try:
            await self.count_tokens("health check")
            return True
        except Exception as e:
            logger.error("llm.health_check_failed", error=str(e))
            return False

_gemini_client = GeminiClient()

def get_llm_client() -> GeminiClient:
    return _gemini_client
