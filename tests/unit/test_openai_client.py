import pytest
import asyncio
from app.core.openai_client import OpenAIClient

class DummyResponse:
    def __init__(self, content):
        self._content = content
    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}
    def raise_for_status(self):
        pass

@pytest.mark.asyncio
async def test_ask_llm(monkeypatch):
    async def fake_post(*args, **kwargs):
        class FakeClient:
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc, tb): pass
            async def post(self, *a, **k):
                return DummyResponse('{"result": "ok"}')
        return FakeClient()
    monkeypatch.setattr("httpx.AsyncClient", fake_post)
    client = OpenAIClient(api_key="test-key", model="gpt-4o-mini")
    result = await client.ask_llm("prompt")
    assert result["result"] == "ok"
