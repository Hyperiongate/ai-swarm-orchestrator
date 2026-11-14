"""
Speech Fact-Checker — stand-in for the AI service (TESTS ONLY)
File: tests/factcheck/stub_ai_service.py
Created: November 11, 2026
Last Updated: November 13, 2026 — also stands in for the panel's AI services

PURPOSE:
    A tiny local web service that answers like the Anthropic Messages API, so
    the fact-checker can be tested end to end (real engine, real helper
    process, real Anthropic library) without an AI key and without spending
    money. The tests point the library at it with ANTHROPIC_BASE_URL.

    Nothing in the Swarm imports this file. Its "verdicts" are scripted from
    keywords in the claim and mean nothing about the real world:
        wrong -> false      half / flip -> misleading      unknown -> unverified
        pausecase   -> first reply is a paused search, then the answer
        nudgecase   -> first reply forgets to record its answer
        neveranswer -> never records an answer
        slowcase    -> takes STUB_SLOW_SECONDS (default 12) to answer
        autherror   -> the service rejects the key (401)

    Added November 13, 2026: it also answers like the three services the
    fact-checker's panel asks (factcheck_panel.py), each under its own path:
        /gpt/chat/completions        (OpenAI style)
        /deepseek/chat/completions   (OpenAI style)
        /gemini/<version>/models/<model>:generateContent
    Panel verdicts follow the same keywords, plus:
        dispute     -> GPT answers "misleading" whatever the others say
        geminidown  -> Gemini answers 402 (out of credit)
        garble      -> DeepSeek answers with text that is not the asked-for JSON
    GET /_panel returns the last request bodies the panel services received.

    Usage:  python tests/factcheck/stub_ai_service.py [port]
    GET /_stats returns how many calls were made and the last request bodies.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import os
import re
import sys
import time

from flask import Flask, jsonify, request

app = Flask(__name__)
STATS = {"calls": 0, "last": []}
PANEL = {"calls": 0, "last": []}
DELAY = float(os.environ.get("STUB_DELAY", "0.25"))
SLOW = float(os.environ.get("STUB_SLOW_SECONDS", "12"))

SEARCH_BLOCKS = [
    {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {"query": "x"}},
    {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": [
        {"type": "web_search_result", "url": "https://stats.example.gov/report",
         "title": "Official statistics", "encrypted_content": "abc", "page_age": None},
        {"type": "web_search_result", "url": "https://news.example.org/story/",
         "title": "News story", "encrypted_content": "def", "page_age": None},
    ]},
]


def _section(text, tag):
    match = re.search(rf"<{tag}>\n?(.*?)\n?</{tag}>", text, re.S)
    return match.group(1).strip() if match else ""


def _message(content, stop_reason, searches=0, model="stub"):
    return jsonify({
        "id": "msg_stub", "type": "message", "role": "assistant", "model": model,
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 1000, "output_tokens": 200,
                  "server_tool_use": {"web_search_requests": searches}},
    })


def _tool_use(name, answer):
    return {"type": "tool_use", "id": "toolu_stub", "name": name, "input": answer}


@app.get("/_stats")
def stats():
    return jsonify(STATS)


@app.post("/v1/messages")
def messages():
    body = request.get_json()
    STATS["calls"] += 1
    STATS["last"] = (STATS["last"] + [body])[-12:]
    time.sleep(DELAY)

    names = [tool.get("name") for tool in body.get("tools", [])]
    turns = body["messages"]
    first = turns[0]["content"]
    user_text = first if isinstance(first, str) else " ".join(
        part.get("text", "") for part in first if isinstance(part, dict))
    model = body.get("model", "stub")

    # The special keywords act on the claim being checked, not on claim-finding.
    claim = _section(user_text, "claim")
    if "autherror" in claim:
        return jsonify({"type": "error", "error": {"type": "authentication_error",
                                                   "message": "invalid x-api-key"}}), 401
    if "slowcase" in claim:
        time.sleep(SLOW)

    if "record_claims" in names:
        passage = _section(user_text, "new_passage")
        ended = "The speech has ended" in user_text
        claims = []
        for sentence in re.split(r"(?<=[.!?])\s+", passage):
            sentence = sentence.strip()
            if re.search(r"\d", sentence) and sentence.endswith((".", "!", "?")):
                kind = "attribution" if " said " in sentence else "content"
                claims.append({"quote": sentence, "claim": "CLAIM: " + sentence, "kind": kind})
        tail = ""
        if passage and not passage.rstrip().endswith((".", "!", "?")) and not ended:
            tail = re.split(r"(?<=[.!?])\s+", passage)[-1]
        return _message([_tool_use("record_claims", {"claims": claims, "incomplete_tail": tail})],
                        "tool_use", model=model)

    if "record_verdict" in names:
        if "pausecase" in claim and len(turns) == 1:
            return _message(SEARCH_BLOCKS, "pause_turn", 1, model)
        if "neveranswer" in claim:
            return _message([{"type": "text", "text": "I looked into it."}], "end_turn", 0, model)
        if "nudgecase" in claim and len(turns) == 1:
            return _message(SEARCH_BLOCKS + [{"type": "text", "text": "Here is what I found."}],
                            "end_turn", 1, model)
        verdict = "true"
        if "wrong" in claim:
            verdict = "false"
        elif "half" in claim:
            verdict = "misleading"
        elif "unknown" in claim:
            verdict = "unverified"
        prior = [] if len(turns) > 1 else SEARCH_BLOCKS
        return _message(prior + [_tool_use("record_verdict", {
            "verdict": verdict, "reason": "Scripted test reason.", "literal": "Scripted literal.",
            "implied_claim": "Scripted implied claim.", "confidence": "medium",
            "source_urls": ["https://stats.example.gov/report/",
                            "https://made-up.example.com/never-searched"],
            "evidence": "Scripted evidence: the official figure was 5 in 2025.",
        })], "tool_use", 1 if prior else 0, model)

    if "record_dissection" in names:
        final = "false" if "wrong" in claim else ("misleading" if ("half" in claim or "flip" in claim) else "true")
        return _message(SEARCH_BLOCKS + [_tool_use("record_dissection", {
            "final_verdict": final, "final_reason": "Scripted deep reason.",
            "literal_verdict": "true", "literal_explanation": "Scripted literal explanation.",
            "implied_claim": "Scripted implied claim.", "implied_verdict": final,
            "implied_explanation": "Scripted implied explanation.",
            "track_record_found": False, "track_record": "",
            "techniques": [{"name": "Missing context", "explanation": "Scripted technique."}],
            "context": "Scripted context.", "confidence": "high",
            "source_urls": ["https://news.example.org/story"],
        })], "tool_use", 2, model)

    return jsonify({"type": "error", "error": {"type": "invalid_request_error",
                                               "message": "unexpected request to the stub"}}), 400


# ---------------------------------------------------------------------------
# the panel's services (added November 13, 2026)
# ---------------------------------------------------------------------------

def _panel_verdict(who, text):
    claim = _section(text, "claim")
    verdict = "false" if "wrong" in claim else ("misleading" if "half" in claim else
                                                ("unverified" if "unknown" in claim else "true"))
    if who == "gpt" and "dispute" in claim:
        verdict = "misleading"
    return claim, {"verdict": verdict, "confidence": "high", "reason": f"Scripted {who} reason."}


def _record_panel(who, body):
    PANEL["calls"] += 1
    PANEL["last"] = (PANEL["last"] + [{"who": who, "body": body}])[-12:]
    time.sleep(DELAY)


@app.get("/_panel")
def panel_stats():
    return jsonify(PANEL)


@app.post("/<who>/chat/completions")
def chat_completions(who):
    body = request.get_json()
    _record_panel(who, body)
    user_text = body["messages"][-1]["content"]
    claim, answer = _panel_verdict(who, user_text)
    content = "I would rather chat about it." if (who == "deepseek" and "garble" in claim) else json.dumps(answer)
    return jsonify({"id": "c1", "object": "chat.completion", "created": 1, "model": body.get("model"),
                    "choices": [{"index": 0, "finish_reason": "stop",
                                 "message": {"role": "assistant", "content": content}}],
                    "usage": {"prompt_tokens": 400, "completion_tokens": 30, "total_tokens": 430}})


@app.post("/gemini/<version>/models/<path:model_and_action>")
def gemini(version, model_and_action):
    body = request.get_json()
    _record_panel("gemini", body)
    user_text = json.dumps(body.get("contents"))
    user_text = body["contents"][0]["parts"][0]["text"] if isinstance(body.get("contents"), list) else user_text
    claim, answer = _panel_verdict("gemini", user_text)
    if "geminidown" in claim:
        return jsonify({"error": {"code": 402, "message": "Your prepayment credits are depleted.",
                                  "status": "RESOURCE_EXHAUSTED"}}), 402
    return jsonify({"candidates": [{"content": {"role": "model", "parts": [{"text": json.dumps(answer)}]},
                                    "finishReason": "STOP", "index": 0}],
                    "usageMetadata": {"promptTokenCount": 400, "candidatesTokenCount": 30, "totalTokenCount": 430}})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5099
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)

# I did no harm and this file is not truncated
