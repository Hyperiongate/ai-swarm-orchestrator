"""
The Humanity Index — stand-in for the AI services (TESTS ONLY)
File: tests/humanity/stub_ai_service.py
Created: November 15, 2026
Last Updated: November 15, 2026 (afternoon) — also answers score research

PURPOSE:
    A tiny local web service that answers like the Anthropic Messages API and
    like the three services on the review panel (GPT, DeepSeek, Gemini), so
    the Humanity Index can be tested end to end (real engine, real helper
    process, real AI libraries) without keys and without spending money.
    Nothing in the Swarm imports this file. Its numbers mean nothing.

    Keywords in the question steer it:
        pausecase   first reply is a paused search, then the answer
        neveranswer never records an answer
        badnumbers  answers with junk numbers the engine must clean up
        slowcase    takes STUB_SLOW_SECONDS (default 8) to answer
        autherror   the service rejects the key (401)
    Panel keywords:
        doubt       Gemini rates E1 doubtful (with a better value), GPT rates F1 wrong
        garble      DeepSeek answers with text that is not the asked-for JSON
        geminidown  Gemini answers 402 (out of credit)

    Score research (the record_measures tool) answers with scripted values
    (SCORE_VALUES below; they are NOT real data). Keywords in the place:
        Nodataville    nothing is found for any measure
        Brokenville    the Science category never records an answer
        Fakelinkton    every value cites a page the search never returned
    In score reviews, 'Doubtburg' makes GPT rate life expectancy wrong.

    Usage:  python tests/humanity/stub_ai_service.py [port]
    GET /_stats returns the call counts and the last request bodies.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import os
import re
import sys
import time

from flask import Flask, jsonify, request

app = Flask(__name__)
STATS = {"calls": 0, "panel_calls": 0, "last": [], "panel_last": []}
DELAY = float(os.environ.get("STUB_DELAY", "0.1"))
SLOW = float(os.environ.get("STUB_SLOW_SECONDS", "8"))

SEARCH_BLOCKS = [
    {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {"query": "x"}},
    {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": [
        {"type": "web_search_result", "url": "https://stats.example.gov/transport",
         "title": "Official transport statistics", "encrypted_content": "abc", "page_age": None},
        {"type": "web_search_result", "url": "https://health.example.org/walking/",
         "title": "Walking and health", "encrypted_content": "def", "page_age": None},
    ]},
]


SCORE_VALUES = {
    "life_expectancy": 73.3, "child_mortality": 37, "hunger": 8.2, "extreme_poverty": 10.5, "safe_water": 74,
    "life_satisfaction": 5.6, "freedom_choices": 80, "personal_freedom": 6.8, "liberal_democracy": 0.25,
    "modern_slavery": 6.4, "gini": 62, "top10_share": 52, "warming": 1.5, "wildlife": 27, "air": 31,
    "emissions": 6.6, "schooling": 8.7, "neet": 20, "rd_spending": 2.6, "researchers": 1400,
    "conflict_deaths": 2.5, "homicide": 5.8, "corruption": 43, "helped_stranger": 61, "donated": 35,
    "volunteered": 23,
}


def _section(text, tag):
    match = re.search(rf"<{tag}>\n?(.*?)\n?</{tag}>", text, re.S)
    return match.group(1).strip() if match else ""


def _question(text):
    match = re.search(r"<question>\n?(.*?)\n?</question>", text, re.S)
    return match.group(1).strip() if match else ""


def _message(content, stop_reason, searches=0, model="stub"):
    return jsonify({
        "id": "msg_stub", "type": "message", "role": "assistant", "model": model,
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 20000, "output_tokens": 3000,
                  "server_tool_use": {"web_search_requests": searches}},
    })


def _good_answer():
    return {
        "title": "Walking instead of driving",
        "understood_as": "You want to know what changes if you walk short trips instead of driving.",
        "area": "Environment and climate",
        "where_we_are": {
            "summary": "Most short trips are made by car. Scripted test summary.",
            "figures": [
                {"label": "Car trips under 2 miles", "value": "45%", "year": "2024",
                 "source_url": "https://stats.example.gov/transport/"},
                {"label": "Adults who get enough exercise", "value": "1 in 4", "year": "2023",
                 "source_url": "https://never-searched.example.com/page"},
            ]},
        "why": {"causes": ["Towns are built around cars.", "Walking feels slower."],
                "disagreement": "Estimates of emissions per mile range from 0.3 to 0.45 kg."},
        "action": {"label": "Walk instead of driving", "one_time": "one 2-mile trip",
                   "default_times_per_week": 5, "assumptions": "An average petrol car."},
        "effects": [
            {"label": "CO2 kept out of the air", "kind": "environment", "unit": "kg of CO2",
             "per_time": 0.8, "basis": "2 miles at 0.4 kg per mile.",
             "source_url": "https://stats.example.gov/transport",
             "picture_it": {"label": "cars driven for a year", "units_per_item": 4600}},
            {"label": "Calories burned", "kind": "health", "unit": "calories", "per_time": 200,
             "basis": "About 100 calories a mile.", "source_url": "https://health.example.org/walking"},
        ],
        "everyone_who_could": {"people": 1400000000, "who": "people who drive regularly",
                               "source_url": "https://stats.example.gov/transport"},
        "comparisons": [],
        "at_scale": "Fewer cars also means less traffic and cleaner air.",
        "big_lever": "Safer streets for walking.",
        "honest_limits": "Your own car and route will differ.",
        "source_urls": ["https://stats.example.gov/transport", "https://made-up.example.com/x"],
    }


def _bad_answer():
    answer = _good_answer()
    answer["area"] = "Not a real area"
    answer["action"]["default_times_per_week"] = 999
    answer["effects"][0]["per_time"] = "lots"
    answer["effects"][1]["kind"] = "nonsense"
    answer["effects"][1]["picture_it"] = {"label": "x", "units_per_item": -5}
    answer["everyone_who_could"]["people"] = 1e15
    answer["where_we_are"]["figures"].append({"label": "", "value": "9"})
    return answer


@app.get("/_stats")
def stats():
    return jsonify(STATS)


@app.post("/v1/messages")
def messages():
    body = request.get_json()
    STATS["calls"] += 1
    STATS["last"] = (STATS["last"] + [body])[-6:]
    time.sleep(DELAY)
    turns = body["messages"]
    first = turns[0]["content"]
    text = first if isinstance(first, str) else " ".join(p.get("text", "") for p in first if isinstance(p, dict))
    question = _question(text)
    model = body.get("model", "stub")
    if "record_measures" in [t.get("name") for t in body.get("tools", [])]:
        return _measures(text, turns, model)
    if "autherror" in question:
        return jsonify({"type": "error", "error": {"type": "authentication_error",
                                                   "message": "invalid x-api-key"}}), 401
    if "slowcase" in question:
        time.sleep(SLOW)
    if "pausecase" in question and len(turns) == 1:
        return _message(SEARCH_BLOCKS, "pause_turn", 1, model)
    if "neveranswer" in question:
        return _message([{"type": "text", "text": "I looked into it."}], "end_turn", 0, model)
    answer = _bad_answer() if "badnumbers" in question else _good_answer()
    prior = [] if len(turns) > 1 else SEARCH_BLOCKS
    return _message(prior + [{"type": "tool_use", "id": "toolu_stub", "name": "record_humanity_answer",
                              "input": answer}], "tool_use", 1 if prior else 0, model)


def _measures(text, turns, model):
    place = _section(text, "place")
    category = _section(text, "category")
    keys = re.findall(r"- key: (\w+)", text)
    if "Brokenville" in place and category == "Science and discovery":
        return _message([{"type": "text", "text": "I could not find it."}], "end_turn", 0, model)
    values = []
    for key in keys:
        if "Nodataville" in place:
            values.append({"key": key, "found": False})
            continue
        url = "https://never-searched.example.com/x" if "Fakelinkton" in place else "https://stats.example.gov/transport"
        values.append({"key": key, "found": True, "value": SCORE_VALUES.get(key, 50), "year": "2024",
                       "level": "world" if place == "World" else "county", "where": place,
                       "note": "Scripted test value.", "source_url": url})
    prior = [] if len(turns) > 1 else SEARCH_BLOCKS
    return _message(prior + [{"type": "tool_use", "id": "toolu_stub", "name": "record_measures",
                              "input": {"values": values}}], "tool_use", 1 if prior else 0, model)


# ---------------------------------------------------------------------------
# the review panel's services
# ---------------------------------------------------------------------------

def _ratings(who, text):
    ids = re.findall(r"^([A-Z][A-Z0-9]*)\. ", text, re.M)
    question = _question(text) or _section(text, "place")
    out = []
    for item_id in ids:
        rating, better = "sound", ""
        if "doubt" in question and who == "gemini" and item_id == "E1":
            rating, better = "doubtful", "0.6 kg"
        if "doubt" in question and who == "gpt" and item_id == "F1":
            rating, better = "wrong", "30%"
        if "Doubtburg" in question and who == "gpt" and item_id == "M1":
            rating, better = "wrong", "71"
        out.append({"id": item_id, "rating": rating, "note": f"Scripted {who} note.", "better_value": better})
    return question, {"ratings": out}


def _record_panel(who, body):
    STATS["panel_calls"] += 1
    STATS["panel_last"] = (STATS["panel_last"] + [{"who": who, "body": body}])[-6:]
    time.sleep(DELAY)


@app.post("/<who>/chat/completions")
def chat_completions(who):
    body = request.get_json()
    _record_panel(who, body)
    question, answer = _ratings(who, body["messages"][-1]["content"])
    content = "Happy to chat about it." if (who == "deepseek" and "garble" in question) else json.dumps(answer)
    return jsonify({"id": "c1", "object": "chat.completion", "created": 1, "model": body.get("model"),
                    "choices": [{"index": 0, "finish_reason": "stop",
                                 "message": {"role": "assistant", "content": content}}],
                    "usage": {"prompt_tokens": 900, "completion_tokens": 120, "total_tokens": 1020}})


@app.post("/gemini/<version>/models/<path:model_and_action>")
def gemini(version, model_and_action):
    body = request.get_json()
    _record_panel("gemini", body)
    text = body["contents"][0]["parts"][0]["text"]
    question, answer = _ratings("gemini", text)
    if "geminidown" in question:
        return jsonify({"error": {"code": 402, "message": "Your prepayment credits are depleted.",
                                  "status": "RESOURCE_EXHAUSTED"}}), 402
    return jsonify({"candidates": [{"content": {"role": "model", "parts": [{"text": json.dumps(answer)}]},
                                    "finishReason": "STOP", "index": 0}],
                    "usageMetadata": {"promptTokenCount": 900, "candidatesTokenCount": 120,
                                      "totalTokenCount": 1020}})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5098
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)

# I did no harm and this file is not truncated
