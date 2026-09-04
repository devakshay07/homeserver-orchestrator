import asyncio
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import structlog
from typing import Optional

from config.settings import settings

logger = structlog.get_logger("app")

class GeminiError(Exception): pass
class GeminiQuotaExhausted(GeminiError): pass
class GeminiContentBlocked(GeminiError): pass

class GeminiClient:
    # Free-tier verified model IDs — do not use non-existent model names
    MODEL_FALLBACK_CHAIN = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]

    def __init__(self):
        self.keys = settings.get_gemini_keys()
        if not self.keys:
            raise ValueError("No Gemini keys provided")
        self._current_idx = -1  # start at -1 so first _get_next_key() returns index 0
        self._lock = asyncio.Lock()

        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

    async def _get_next_key(self) -> tuple[int, str]:
        async with self._lock:
            self._current_idx = (self._current_idx + 1) % len(self.keys)
            logger.info("Rotated Gemini API key", new_idx=self._current_idx)
            return self._current_idx, self.keys[self._current_idx]

    async def _call_api(self, model_name: str, key: str, prompt: str, system_instruction: Optional[str] = None, media_data: Optional[dict] = None) -> str:
        # Hold lock only for global configure() + model creation; release before network I/O
        async with self._lock:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction
            )
            contents = [prompt]
            if media_data:
                contents.insert(0, media_data)
        # Lock released — concurrent calls can now configure their own model
        response = await model.generate_content_async(
            contents,
            safety_settings=self.safety_settings
        )
        if response.parts:
            return response.text
        return ""

    async def generate_content(self, model_name: str, prompt: str, system_instruction: Optional[str] = None, media_data: Optional[dict] = None) -> str:
        for model in self._get_model_chain(model_name):
            keys_tried: set[int] = set()
            backoff = 2
            
            for attempt in range(settings.max_retries * len(self.keys)):
                key_idx, key = await self._get_next_key()
                try:
                    return await self._call_api(model, key, prompt, system_instruction, media_data)
                except Exception as e:
                    error_msg = str(e).lower()
                    logger.warning("Gemini API error", attempt=attempt, error=error_msg, model=model)
                    
                    if "blocked" in error_msg or "safety" in error_msg:
                        raise GeminiContentBlocked(f"Content blocked by safety filters: {error_msg}")
                    
                    if "429" in error_msg or "quota" in error_msg:
                        keys_tried.add(key_idx)
                        if len(keys_tried) >= len(self.keys):
                            break  # all keys exhausted -> try next model
                    
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    
        raise GeminiQuotaExhausted(f"All keys and model fallbacks exhausted for {model_name}")

    def _get_model_chain(self, requested: str) -> list[str]:
        try:
            idx = self.MODEL_FALLBACK_CHAIN.index(requested)
            return self.MODEL_FALLBACK_CHAIN[idx:]
        except ValueError:
            return [requested] + self.MODEL_FALLBACK_CHAIN
