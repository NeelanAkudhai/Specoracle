import os
import time
import json
import sqlite3
import hashlib
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from .schemas import LLMResult

class _RateLimiter:
    """Thread-safe sliding-window rate limiter: max `rpm` calls per 60s."""
    def __init__(self, rpm: int):
        self.rpm = max(1, rpm)
        self._events: List[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        if self.rpm <= 0:
            return
        while True:
            with self._lock:
                now = time.time()
                self._events = [t for t in self._events if now - t < 60.0]
                if len(self._events) < self.rpm:
                    self._events.append(now)
                    return
                sleep_for = 60.0 - (now - self._events[0]) + 0.05
            time.sleep(max(0.05, sleep_for))

class LLMClient:
    """
    OpenAI-compatible client (configured for Groq) with:
    1. Persistent SQLite caching keyed by sha256(model + messages + temp + max_tokens).
    2. Thread-safe sliding-window RPM rate limiter.
    3. Exponential backoff retry logic for 429 rate limits and 5xx server errors.
    4. Deterministic offline mock mode for zero-cost testing and development.
    """
    def __init__(
        self,
        base_url: str = "https://api.groq.com/openai/v1",
        api_key: Optional[str] = None,
        cache_db: str | Path = "cache/llm_cache.sqlite",
        rpm: int = 25,
        mock: bool = False
    ):
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
        self.cache_db = Path(cache_db)
        self.rpm = rpm
        self.mock = mock
        self._limiter = _RateLimiter(rpm)
        self._mem_cache: Dict[str, LLMResult] = {}
        
        self.cache_db.parent.mkdir(parents=True, exist_ok=True)
        self._init_cache()

        self._client = None
        if not self.mock and self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            except ImportError:
                self.mock = True

    def _init_cache(self):
        try:
            with sqlite3.connect(self.cache_db) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache (
                        cache_key TEXT PRIMARY KEY,
                        response_text TEXT,
                        prompt_tokens INTEGER,
                        completion_tokens INTEGER,
                        latency REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except sqlite3.OperationalError:
            fallback_db = Path("/tmp") / self.cache_db.name
            try:
                with sqlite3.connect(fallback_db) as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS cache (
                            cache_key TEXT PRIMARY KEY,
                            response_text TEXT,
                            prompt_tokens INTEGER,
                            completion_tokens INTEGER,
                            latency REAL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    conn.commit()
                self.cache_db = fallback_db
            except Exception:
                self._mem_cache = {}

    def _get_cache(self, key: str) -> Optional[LLMResult]:
        if key in self._mem_cache:
            return self._mem_cache[key]
        try:
            with sqlite3.connect(self.cache_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT response_text, prompt_tokens, completion_tokens, latency FROM cache WHERE cache_key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                if row:
                    return LLMResult(
                        text=row[0],
                        prompt_tokens=row[1],
                        completion_tokens=row[2],
                        latency=row[3],
                        cached=True
                    )
        except Exception:
            pass
        return None

    def _set_cache(self, key: str, res: LLMResult):
        self._mem_cache[key] = res
        try:
            with sqlite3.connect(self.cache_db) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache (cache_key, response_text, prompt_tokens, completion_tokens, latency)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (key, res.text, res.prompt_tokens, res.completion_tokens, res.latency)
                )
                conn.commit()
        except Exception:
            pass

    def _generate_mock_response(self, model: str, messages: List[Dict[str, str]]) -> str:
        """Generates realistic synthetic responses for offline smoke testing."""
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        
        if "reference implementation" in user_msg.lower() or "def " in user_msg:
            import re
            m = re.search(r"def\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)", user_msg)
            if m:
                fn_name = m.group(1)
                args = m.group(2)
                return f"""```python
def {fn_name}({args}):
    if '{fn_name}' == 'has_close_elements':
        for i in range(len(numbers)):
            for j in range(i + 1, len(numbers)):
                if abs(numbers[i] - numbers[j]) < threshold:
                    return True
        return False
    elif '{fn_name}' == 'truncate_number':
        return number % 1.0
    elif '{fn_name}' == 'below_zero':
        b = 0
        for op in operations:
            b += op
            if b < 0:
                return True
        return False
    elif '{fn_name}' == 'separate_paren_groups':
        return ['()', '(())', '(()())']
    elif '{fn_name}' == 'mean_absolute_deviation':
        m = sum(numbers) / len(numbers)
        return sum(abs(x - m) for x in numbers) / len(numbers)
    return None
```"""

        return """[
  {"args": [[1.0, 2.0, 3.9], 0.3], "expected": false},
  {"args": [[1.0, 2.0, 3.0], 0.5], "expected": false},
  {"args": [[1.0, 2.8, 3.0], 0.3], "expected": true},
  {"args": [[], 0.5], "expected": false},
  {"args": [[1.0], 1.0], "expected": false}
]"""

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096
    ) -> LLMResult:
        cache_content = model + json.dumps(messages, sort_keys=True) + str(temperature) + str(max_tokens)
        cache_key = hashlib.sha256(cache_content.encode("utf-8")).hexdigest()

        cached_result = self._get_cache(cache_key)
        if cached_result:
            return cached_result

        if self.mock or not self._client:
            mock_text = self._generate_mock_response(model, messages)
            res = LLMResult(
                text=mock_text,
                prompt_tokens=150,
                completion_tokens=100,
                latency=0.05,
                cached=False
            )
            self._set_cache(cache_key, res)
            return res

        max_retries = 8
        delay = 1.0
        start_time = time.time()

        for attempt in range(max_retries):
            self._limiter.acquire()
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                text = response.choices[0].message.content or ""
                if not text.strip():
                    raise ValueError("Received empty content from LLM completion")

                latency = time.time() - start_time
                usage = response.usage
                p_tokens = usage.prompt_tokens if usage else 0
                c_tokens = usage.completion_tokens if usage else 0

                res = LLMResult(
                    text=text,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    latency=latency,
                    cached=False
                )
                self._set_cache(cache_key, res)
                return res

            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "rate limit" in err_str
                is_server_error = "500" in err_str or "503" in err_str or "overloaded" in err_str
                
                if (is_rate_limit or is_server_error) and attempt < max_retries - 1:
                    time.sleep(delay)
                    delay = min(delay * 2.0, 60.0)
                else:
                    raise RuntimeError(f"LLM request failed after {attempt+1} attempts: {str(e)}")

        raise RuntimeError("LLM request exhausted retry limit")
