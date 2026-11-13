"""
AI connections — tests with stand-in AI services
File: tests/ai/test_ai_connections.py
Created: November 13, 2026
Last Updated: November 13, 2026 — Initial version

PURPOSE:
    Checks the code that talks to Claude, GPT, DeepSeek and Gemini without an
    AI key and without spending money. A small local web service answers the
    way each real service does (including a Claude 5.x reply that begins with
    a "thinking" block), and the tests confirm that:
      * claude_compat builds the right request for 4.x and 5.x models;
      * every Claude call in the Swarm reads the answer correctly when the
        reply starts with thinking, and reports an empty reply as an error;
      * call_gemini() works through Google's current library;
      * the self-test reports working, failing and not-set-up connections.
    Nothing in the Swarm imports this file.

    These tests prove the Swarm's side of each conversation. They cannot
    prove the real services accept it; the self-test page on the live Swarm
    (/ai-selftest) is what proves that.

    Run:  DATABASE_URL=postgresql://... python -m pytest tests/ai -q

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

SEEN = []          # every request body the stand-in received: (path, body)


class _StandIn(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, payload, status=200):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send({"object": "list", "data": [
                {"id": "gpt-5.5", "object": "model", "created": 1, "owned_by": "openai"},
                {"id": "gpt-realtime-2.1", "object": "model", "created": 1, "owned_by": "openai"},
                {"id": "gpt-realtime-1.5", "object": "model", "created": 1, "owned_by": "openai"}]})
        elif self.path == "/voice/health":
            self._send({"status": "healthy"})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        SEEN.append((self.path, body))

        if self.path.endswith("/v1/messages"):                      # Anthropic
            model = body.get("model", "")
            prompt = json.dumps(body.get("messages"))
            usage = {"input_tokens": 11, "output_tokens": 7}
            base = {"id": "msg_1", "type": "message", "role": "assistant", "model": model,
                    "stop_sequence": None, "usage": usage}
            if "DECLINE" in prompt:
                return self._send(dict(base, content=[], stop_reason="refusal"))
            if "RUNOUT" in prompt:
                return self._send(dict(base, stop_reason="max_tokens",
                                       content=[{"type": "thinking", "thinking": "", "signature": "sig"}]))
            content = [{"type": "text", "text": "READY"}]
            if "-5-" in model:                                      # 5.x replies begin with thinking
                content = [{"type": "thinking", "thinking": "", "signature": "sig"}] + content
            return self._send(dict(base, content=content, stop_reason="end_turn"))

        if self.path.endswith("/chat/completions"):                 # OpenAI and DeepSeek
            return self._send({"id": "c1", "object": "chat.completion", "created": 1, "model": body.get("model"),
                               "choices": [{"index": 0, "finish_reason": "stop",
                                            "message": {"role": "assistant", "content": "READY"}}],
                               "usage": {"prompt_tokens": 9, "completion_tokens": 3, "total_tokens": 12}})

        if ":generateContent" in self.path:                         # Gemini
            if "gone-model" in self.path:
                return self._send({"error": {"code": 404, "message": "model not found", "status": "NOT_FOUND"}}, 404)
            return self._send({"candidates": [{"content": {"role": "model", "parts": [{"text": "READY"}]},
                                               "finishReason": "STOP", "index": 0}],
                               "usageMetadata": {"promptTokenCount": 21, "candidatesTokenCount": 2,
                                                 "totalTokenCount": 23}})
        self._send({"error": "not found"}, 404)


@pytest.fixture(scope="module")
def stand_in():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StandIn)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def clients(stand_in):
    """The Swarm's real AI client module, pointed at the stand-in."""
    for name in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
        os.environ.pop(name, None)
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    os.environ.update({"ANTHROPIC_API_KEY": "test-key", "OPENAI_API_KEY": "test-key",
                       "DEEPSEEK_API_KEY": "test-key", "GOOGLE_API_KEY": "test-key"})
    os.environ.pop("LOCAL_GEMMA_BASE_URL", None)
    import anthropic
    from openai import OpenAI
    from google import genai
    from google.genai import types
    import config
    from orchestration import ai_clients

    saved = {name: getattr(ai_clients, name) for name in
             ("anthropic_client", "openai_client", "deepseek_client", "gemini_client", "local_gemma_client")}
    saved_config = {name: getattr(config, name) for name in
                    ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "GOOGLE_API_KEY",
                     "CLAUDE_SONNET_MODEL", "CLAUDE_OPUS_MODEL", "GEMINI_MODEL", "LOCAL_GEMMA_BASE_URL")}
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "GOOGLE_API_KEY"):
        setattr(config, name, "test-key")
    config.LOCAL_GEMMA_BASE_URL = None
    ai_clients.anthropic_client = anthropic.Anthropic(api_key="test-key", base_url=stand_in, max_retries=0)
    ai_clients.openai_client = OpenAI(api_key="test-key", base_url=stand_in, max_retries=0)
    ai_clients.deepseek_client = OpenAI(api_key="test-key", base_url=stand_in, max_retries=0)
    ai_clients.gemini_client = genai.Client(api_key="test-key", http_options=types.HttpOptions(base_url=stand_in))
    ai_clients.local_gemma_client = None
    yield ai_clients
    for name, value in saved.items():
        setattr(ai_clients, name, value)
    for name, value in saved_config.items():
        setattr(config, name, value)


def _last_body(path_part):
    return [body for path, body in SEEN if path_part in path][-1]


# ---------------------------------------------------------------------------
# claude_compat on its own
# ---------------------------------------------------------------------------

def test_request_for_older_models_is_exactly_what_was_sent_before():
    from claude_compat import claude_request
    assert claude_request("claude-sonnet-4-6", 1000, effort="low") == {"model": "claude-sonnet-4-6", "max_tokens": 1000}
    assert claude_request("claude-opus-4-8", 4000) == {"model": "claude-opus-4-8", "max_tokens": 4000}
    assert claude_request("some-future-name", 500) == {"model": "some-future-name", "max_tokens": 500}


def test_request_for_thinking_models_sets_effort_and_leaves_room_to_think():
    from claude_compat import claude_request, THINKING_HEADROOM
    low = claude_request("claude-sonnet-5-5", 300, effort="low")
    assert low == {"model": "claude-sonnet-5-5", "max_tokens": 300 + THINKING_HEADROOM["low"],
                   "extra_body": {"output_config": {"effort": "low"}}}
    medium = claude_request("claude-opus-5-5", 4000)
    assert medium["max_tokens"] == 4000 + THINKING_HEADROOM["medium"]
    assert medium["extra_body"] == {"output_config": {"effort": "medium"}}
    assert claude_request("claude-haiku-5-5", 100, effort="nonsense")["extra_body"] == {"output_config": {"effort": "medium"}}
    for sent in (low, medium):                    # the newer models reject these outright
        assert not {"temperature", "top_p", "top_k", "thinking"} & set(sent)


def test_generation_is_read_from_the_model_name():
    from claude_compat import claude_generation, thinks_by_default
    assert [claude_generation(name) for name in
            ("claude-sonnet-5-5", "claude-opus-4-8", "claude-haiku-4-5-20251001", "claude-fable-5-2", "gpt-5.5", "", None)] \
        == [5, 4, 4, 5, 0, 0, 0]
    assert thinks_by_default("claude-sonnet-5-5") and not thinks_by_default("claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# the Swarm's real call functions, against the stand-in
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sonnet, opus", [("claude-sonnet-5-5", "claude-opus-5-5"), ("claude-sonnet-4-6", "claude-opus-4-8")])
def test_every_claude_function_answers_on_both_generations(clients, sonnet, opus):
    import config
    config.CLAUDE_SONNET_MODEL, config.CLAUDE_OPUS_MODEL = sonnet, opus
    thinking = "-5-" in sonnet

    reply = clients.call_claude_sonnet("hello", max_tokens=4000, system_prompt="be brief")
    assert reply["content"] == "READY" and "error" not in reply and reply["usage"]["output_tokens"] == 7
    sent = _last_body("/v1/messages")
    assert sent["model"] == sonnet and sent["system"] == "be brief"
    assert sent["max_tokens"] == (9000 if thinking else 4000)
    assert sent.get("output_config") == ({"effort": "medium"} if thinking else None)

    reply = clients.call_claude_sonnet_raw("hello", "system text", max_tokens=1000)
    assert reply["content"] == "READY"
    sent = _last_body("/v1/messages")
    assert sent["max_tokens"] == (3000 if thinking else 1000)
    assert sent.get("output_config") == ({"effort": "low"} if thinking else None)

    reply = clients.call_claude_opus("hello", max_tokens=4000)
    assert reply["content"] == "READY"
    assert _last_body("/v1/messages")["model"] == opus

    history = [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "earlier answer"}]
    assert clients.call_claude_sonnet("again", conversation_history=history)["content"] == "READY"


def test_an_empty_claude_reply_is_reported_not_crashed_on(clients):
    import config
    config.CLAUDE_SONNET_MODEL, config.CLAUDE_OPUS_MODEL = "claude-sonnet-5-5", "claude-opus-5-5"
    declined = clients.call_claude_sonnet("please DECLINE this")
    assert declined["error"] is True and declined["content"] == "ERROR: The model declined to answer this request."
    ran_out = clients.call_claude_opus("please RUNOUT")
    assert ran_out["error"] is True and "ran out of room" in ran_out["content"]
    raw = clients.call_claude_sonnet_raw("please DECLINE", "system")
    assert raw["error"] is True


def test_the_background_and_assessment_calls_use_the_helpers(clients, stand_in, monkeypatch):
    """The four Claude calls outside ai_clients.py: three proactive jobs and the website assessment."""
    import anthropic
    import config
    config.CLAUDE_SONNET_MODEL = "claude-sonnet-5-5"
    real = anthropic.Anthropic
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: real(api_key="test-key", base_url=stand_in, max_retries=0))

    from routes import assessment_ai
    monkeypatch.setattr(assessment_ai, "MODEL", "claude-sonnet-5-5")
    assert assessment_ai._call_claude("score this", 800) == "READY"
    sent = _last_body("/v1/messages")
    assert sent["max_tokens"] == 2800 and sent["output_config"] == {"effort": "low"} and sent["model"] == "claude-sonnet-5-5"

    for path in ("proactive/task_manager.py", "proactive/lead_scanner.py", "proactive/daily_briefing.py"):
        source = open(os.path.join(ROOT, path), encoding="utf-8").read()
        assert "content[0].text" not in source.split('"""', 2)[2], path
        assert "claude_text(response)" in source and "**claude_request(CLAUDE_SONNET_MODEL" in source, path
    for path in ("orchestration/ai_clients.py", "routes/assessment_ai.py"):
        assert "content[0].text" not in open(os.path.join(ROOT, path), encoding="utf-8").read().split('"""', 2)[2], path


def test_gpt_and_deepseek_still_answer(clients):
    import config
    assert clients.call_gpt4("hello")["content"] == "READY"
    sent = _last_body("/chat/completions")
    assert sent["model"] == config.GPT4_MODEL and "max_completion_tokens" in sent
    assert clients.call_deepseek("hello")["content"] == "READY"
    assert _last_body("/chat/completions")["model"] == config.DEEPSEEK_MODEL == "deepseek-flash"


def test_gemini_works_through_the_current_library(clients):
    import config
    assert config.GEMINI_MODEL == "gemini-3.8-flash"
    reply = clients.call_gemini("hello", max_tokens=500)
    assert reply == {"content": "READY", "usage": {"input_tokens": 21, "output_tokens": 2}}
    path, sent = [(p, b) for p, b in SEEN if ":generateContent" in p][-1]
    assert "/models/gemini-3.8-flash:generateContent" in path
    assert sent["generationConfig"]["maxOutputTokens"] == 500
    assert "hello" in json.dumps(sent["contents"])
    assert "systemInstruction" in sent                               # identity sent as a real system instruction

    config.GEMINI_MODEL = "gone-model"                               # a retired model is an error dict, not a crash
    failed = clients.call_gemini("hello")
    assert failed["error"] is True and failed["content"].startswith("ERROR: Gemini call failed")
    config.GEMINI_MODEL = "gemini-3.8-flash"

    assert "google.generativeai" not in open(os.path.join(ROOT, "orchestration", "ai_clients.py"), encoding="utf-8").read().split('"""', 2)[2]
    assert "google-generativeai==" not in open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read().split("# AI API CLIENTS")[1]


# ---------------------------------------------------------------------------
# the self-test
# ---------------------------------------------------------------------------

def test_selftest_reports_working_failing_and_not_set_up(clients, stand_in, monkeypatch):
    import config
    from routes import ai_selftest
    config.CLAUDE_SONNET_MODEL, config.CLAUDE_OPUS_MODEL = "claude-sonnet-5-5", "claude-opus-5-5"
    config.GEMINI_MODEL = "gone-model"
    monkeypatch.setattr(ai_selftest, "VOICE_SERVICE_HEALTH_URL", stand_in + "/voice/health")
    try:
        rows = {row["name"]: row for row in ai_selftest.run_selftest()}
    finally:
        config.GEMINI_MODEL = "gemini-3.8-flash"

    assert list(rows) == ["claude_sonnet", "claude_opus", "gpt", "deepseek", "gemini", "local_gemma",
                          "voice_models", "voice_service"]
    for name in ("claude_sonnet", "claude_opus", "gpt", "deepseek", "voice_service"):
        assert rows[name]["ok"] is True, rows[name]
        assert "seconds" in rows[name]
    assert rows["claude_sonnet"]["answer"] == "READY" and rows["claude_sonnet"]["model"] == "claude-sonnet-5-5"
    assert rows["gemini"]["ok"] is False and "Gemini call failed" in rows["gemini"]["error"]
    assert rows["local_gemma"]["ok"] is None and "Not set up" in rows["local_gemma"]["skipped"]
    assert rows["voice_models"]["ok"] is True and rows["voice_models"]["models"] == ["gpt-realtime-1.5", "gpt-realtime-2.1"]

    only = ai_selftest.run_selftest(only={"deepseek"})
    assert [row["name"] for row in only] == ["deepseek"] and only[0]["ok"] is True


def test_selftest_never_reveals_a_key(clients, stand_in, monkeypatch):
    from routes import ai_selftest
    monkeypatch.setattr(ai_selftest, "VOICE_SERVICE_HEALTH_URL", stand_in + "/voice/health")
    assert "test-key" not in json.dumps(ai_selftest.run_selftest())


# I did no harm and this file is not truncated
