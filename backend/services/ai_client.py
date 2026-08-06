"""
AI Client — Gemini (cloud), OpenAI (cloud), or Ollama (local).
Set AI_PROVIDER=gemini|openai|ollama in .env

Chat-only (no embeddings — nothing here needs vector search).
"""
from typing import Any, Dict

import httpx

from core.config import settings


class AIClient:
    def __init__(self):
        self.provider = settings.AI_PROVIDER.lower()
        self.settings = settings

    def chat_json(self, system_prompt: str, user_text: str) -> str:
        """Send a chat request expecting a single JSON object back as raw text."""
        if self.provider == "ollama":
            return self._ollama_chat(system_prompt, user_text)
        if self.provider == "gemini":
            return self._gemini_chat(system_prompt, user_text)
        return self._openai_chat(system_prompt, user_text)

    # --- Ollama (free, local) ---

    def _ollama_chat(self, system_prompt: str, user_text: str) -> str:
        payload: Dict[str, Any] = {
            "model": self.settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "stream": False,
            "format": "json",
            "keep_alive": -1,
        }
        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(f"{self.settings.OLLAMA_BASE_URL}/api/chat", json=payload)
                response.raise_for_status()
                return response.json()["message"]["content"]
        except httpx.ConnectError:
            raise RuntimeError(
                "Ollama is not running. Start it with: ollama serve\n"
                "Or install it from: https://ollama.com/download"
            )

    # --- Google Gemini ---

    def _gemini_chat(self, system_prompt: str, user_text: str) -> str:
        import google.generativeai as genai

        if not self.settings.GEMINI_API_KEY.strip():
            raise RuntimeError("Set GEMINI_API_KEY in backend/.env (get one at aistudio.google.com).")
        genai.configure(api_key=self.settings.GEMINI_API_KEY)
        model_name = (self.settings.GEMINI_MODEL or "gemini-2.5-flash").strip()
        model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
        response = model.generate_content(
            user_text,
            generation_config={"response_mime_type": "application/json"},
        )
        return response.text

    # --- OpenAI (cloud) ---

    def _openai_chat(self, system_prompt: str, user_text: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content
