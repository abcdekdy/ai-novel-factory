"""
LLM客户端 - 支持 LongCat (Anthropic兼容) 和 DeepSeek (OpenAI兼容)
默认使用 LongCat API: https://api.longcat.chat/anthropic
"""

import time

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class LLMClient:
    """
    统一LLM客户端，根据配置自动选择后端
    provider: "longcat" | "deepseek"

    LongCat配置:
        base_url: https://api.longcat.chat/anthropic
        model: (需要根据LongCat实际模型名填写)
        使用 anthropic SDK

    DeepSeek配置:
        base_url: https://api.deepseek.com/v1
        model: deepseek-chat
        使用 openai SDK
    """

    def __init__(self, api_key: str, provider: str = "longcat",
                 base_url: str = None, model: str = None, max_retries: int = 3,
                 timeout: float = 120.0):
        """
        timeout: 单次调用超时秒数（connect + read 合计）。
                 续写大纲等长 prompt 场景建议 ≥ 120s。
        """
        self.api_key = api_key
        self.provider = provider.lower()
        self.max_retries = max_retries
        self.timeout = timeout
        self._streaming_callback = None

        if self.provider == "longcat":
            # Anthropic兼容模式 (LongCat使用Bearer <REDAUTH>)
            if not HAS_ANTHROPIC:
                raise ImportError("请先安装 anthropic SDK: pip install anthropic")
            self.base_url = base_url or "https://api.longcat.chat/anthropic"
            self.model = model or "LongCat-2.0"
            self.client = anthropic.Anthropic(
                auth_token=api_key,   # Bearer <REDAUTH> 方式
                base_url=self.base_url,
                timeout=timeout,
            )
        elif self.provider == "deepseek":
            # OpenAI兼容模式
            if not HAS_OPENAI:
                raise ImportError("请先安装 openai SDK: pip install openai")
            self.base_url = base_url or "https://api.deepseek.com/v1"
            self.model = model or "deepseek-chat"
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=self.base_url,
                max_retries=0,
                timeout=timeout,
            )
        else:
            raise ValueError(f"不支持的provider: {provider}，可选: longcat, deepseek")

    def chat(self, system_prompt: str, user_prompt: str,
             temperature: float = 0.7, max_tokens: int = None) -> str:
        """max_tokens未指定时根据后端自动选择（LongCat思考过程耗token多，默认8192）"""
        if max_tokens is None:
            max_tokens = 8192 if self.provider == "longcat" else 4096
        """
        普通聊天调用
        LongCat (Anthropic格式): system作为单独参数, messages只含user
        DeepSeek (OpenAI格式): messages含system+user
        """
        if self.provider == "longcat":
            return self._chat_anthropic(system_prompt, user_prompt, temperature, max_tokens)
        else:
            return self._chat_openai(system_prompt, user_prompt, temperature, max_tokens)

    def chat_stream(self, system_prompt: str, user_prompt: str,
                    temperature: float = 0.7, max_tokens: int = None,
                    on_chunk=None, on_complete=None):
        """
        流式聊天调用
        """
        if max_tokens is None:
            max_tokens = 8192 if self.provider == "longcat" else 4096
        full_text = ""

        if self.provider == "longcat":
            try:
                kwargs = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "stream": True,
                }
                # 如果base_url不是默认的，需要传入
                if self.base_url != "https://api.longcat.chat/anthropic":
                    kwargs["base_url"] = self.base_url

                with self.client.messages.stream(**kwargs) as stream:
                    for text in stream.text_stream:
                        full_text += text
                        if on_chunk:
                            on_chunk(text, full_text)
            except Exception as e:
                if on_chunk:
                    on_chunk(f"\n[流式输出中断: {e}]", full_text)
        else:
            # DeepSeek
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            try:
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        delta = chunk.choices[0].delta.content
                        full_text += delta
                        if on_chunk:
                            on_chunk(delta, full_text)
            except Exception as e:
                if on_chunk:
                    on_chunk(f"\n[流式输出中断: {e}]", full_text)

        if on_complete:
            on_complete(full_text)
        return full_text

    def _chat_anthropic(self, system_prompt, user_prompt, temperature, max_tokens):
        """Anthropic兼容调用（LongCat）"""
        for attempt in range(self.max_retries):
            try:
                kwargs = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                }
                response = self.client.messages.create(**kwargs)
                # Anthropic返回的是content block列表
                # LongCat可能返回 ThinkingBlock + TextBlock，取TextBlock
                if response.content:
                    for block in response.content:
                        if hasattr(block, 'text') and block.text:
                            return block.text
                return ""
            except anthropic.RateLimitError:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise
            except anthropic.APIError as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                else:
                    raise
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    raise
        return ""

    def _chat_openai(self, system_prompt, user_prompt, temperature, max_tokens):
        """OpenAI兼容调用（DeepSeek）"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content
            except openai.RateLimitError:
                time.sleep(2 ** attempt)
            except openai.APIError:
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                else:
                    raise
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    raise
        return ""

    def set_model(self, model: str):
        self.model = model

    def set_provider(self, provider: str = None, base_url: str = None, model: str = None):
        """切换provider（会重新创建client）"""
        if provider:
            self.provider = provider.lower()
        if base_url:
            self.base_url = base_url
        if model:
            self.model = model

        # 重建client
        if self.provider == "longcat":
            if HAS_ANTHROPIC:
                self.client = anthropic.Anthropic(auth_token=self.api_key, base_url=self.base_url)
        elif self.provider == "deepseek":
            if HAS_OPENAI:
                self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url, max_retries=0)


# ===== 兼容层：保留DeepSeekClient作为别名 =====

class DeepSeekClient(LLMClient):
    """向后兼容的DeepSeek客户端（内部使用LLMClient实现）"""
    def __init__(self, api_key, base_url="https://api.deepseek.com/v1",
                 model="deepseek-chat", max_retries=3):
        super().__init__(api_key=api_key, provider="deepseek",
                        base_url=base_url, model=model, max_retries=max_retries)


# ===== 测试连通性 =====

def test_connection(api_key: str, provider: str = "longcat", base_url: str = None) -> tuple:
    """测试API连通性"""
    try:
        client = LLMClient(api_key=api_key, provider=provider, base_url=base_url)
        response = client.chat(
            system_prompt="You are a helpful assistant.",
            user_prompt="回复'连接成功'三个字，不要多答。",
            max_tokens=50
        )
        return True, f"连接正常：{response.strip()}"
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "Unauthorized" in err_msg or "authentication" in err_msg.lower():
            return False, "API Key无效或认证失败，请检查"
        elif "403" in err_msg or "Forbidden" in err_msg:
            return False, "权限不足，请检查Key的访问权限"
        elif "404" in err_msg:
            return False, "接入点不存在，请检查base_url"
        elif "timeout" in err_msg.lower() or "connection" in err_msg.lower():
            return False, "网络连接超时，请检查网络"
        else:
            return False, f"连接异常：{err_msg[:100]}"
