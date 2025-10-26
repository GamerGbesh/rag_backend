# perplexity_llm.py
from langchain.llms.base import LLM
from typing import Any, List, Optional
import requests
import logging

logger = logging.getLogger(__name__)

class PerplexityLLM(LLM):
    """
    Custom LangChain-compatible wrapper for Perplexity AI chat models.
    You can use this in place of ChatOllama, ChatOpenAI, etc.

    Example:
        llm = PerplexityLLM(api_key="YOUR_KEY", model="pplx-70b-online")
        result = llm.invoke("Explain quantum entanglement")
    """

    api_key: str
    model: str = "pplx-70b-online"
    temperature: float = 0.7
    base_url: str = "https://api.perplexity.ai/chat/completions"

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """Send a chat completion request to the Perplexity API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.exception("Perplexity API call failed: %s", e)
            raise RuntimeError(f"Perplexity API call failed: {str(e)}")

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.model, "temperature": self.temperature}

    @property
    def _llm_type(self) -> str:
        return "perplexity"

    def stream(self, prompt: str):
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "text/event-stream"}
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        with requests.post(self.base_url, json=payload, headers=headers, stream=True) as r:
            for line in r.iter_lines():
                if line and line.startswith(b"data: "):
                    yield line.decode("utf-8").replace("data: ", "")
