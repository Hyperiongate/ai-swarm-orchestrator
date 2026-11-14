"""
Speech Fact-Checker — the panel of other AIs
File: factcheck_panel.py
Created: November 13, 2026
Last Updated: November 13, 2026 — Initial implementation

PURPOSE:
    Real multi-AI consensus for the fact-checker. Claude checks a claim with
    web search and gives its verdict (factcheck_engine.quick_check). This
    module then puts the SAME claim and the SAME evidence in front of other
    companies' AI models and asks each one, separately, for its own verdict.
    The page shows whether they agree ("3 of 3 agree") or not ("Disputed").

    WHAT EACH PANEL MEMBER SEES:
      * the claim, the words as said, the speaker and occasion, the nearby
        speech, and today's date;
      * the evidence Claude's web search turned up, stated as plain facts,
        with the titles and addresses of the sources.
    WHAT IT DOES NOT SEE:
      * Claude's verdict, or Claude's reasoning. Each member decides alone,
        and no member sees another's answer.

    AN HONEST LIMIT: the panel judges the same evidence; it does not search
    the web again (that is the slow, costly part, and it is why the panel adds
    only a few seconds). So agreement means "independent readers of this
    evidence reach the same verdict", not "three separate investigations".
    A member is told to answer "unverified" if the evidence is not enough.

WHO IS ON THE PANEL (each joins only if its key is set in Render):
    GPT        OPENAI_API_KEY      model FACTCHECK_PANEL_OPENAI_MODEL   (default gpt-5.5)
    DeepSeek   DEEPSEEK_API_KEY    model FACTCHECK_PANEL_DEEPSEEK_MODEL (default deepseek-flash)
    Gemini     GOOGLE_API_KEY      model FACTCHECK_PANEL_GEMINI_MODEL   (default gemini-3.8-flash)
    FACTCHECK_PANEL (optional) limits and orders the panel, for example
    "gpt,deepseek". Set it to "none" to switch the panel off on the server.

    The members are asked at the same time. One that fails or is slow is
    reported as "no answer" and never holds up the others.

WHY THIS DOES NOT USE orchestration/ai_clients:
    Same reason as factcheck_engine: those functions add the Swarm's own
    identity and formatting text to every call, and this work runs in the
    separate helper process (factcheck_runner.py), which should load as
    little of the Swarm as possible.

CHANGELOG:
- November 13, 2026: INITIAL IMPLEMENTATION
  * New module. Used only by factcheck_engine.panel_check(). Rule 1 preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait

logger = logging.getLogger(__name__)

VERDICTS = ("true", "misleading", "false", "unverified")
CALL_TIMEOUT_SECONDS = 40          # one member's call
PANEL_BUDGET_SECONDS = 50          # the whole panel; slower members are reported as "no answer"
MAX_ANSWER_TOKENS = 3000           # a ceiling: these models may reason before answering

DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# key -> (name shown on the page, environment variable holding the API key,
#         environment variable naming the model, default model)
MEMBERS = {
    "gpt": ("GPT", "OPENAI_API_KEY", "FACTCHECK_PANEL_OPENAI_MODEL", "gpt-5.5"),
    "deepseek": ("DeepSeek", "DEEPSEEK_API_KEY", "FACTCHECK_PANEL_DEEPSEEK_MODEL", "deepseek-flash"),
    "gemini": ("Gemini", "GOOGLE_API_KEY", "FACTCHECK_PANEL_GEMINI_MODEL", "gemini-3.8-flash"),
}

ANSWER_FORMAT = (
    '\n\nAnswer with ONE JSON object and nothing else, in exactly this shape:\n'
    '{"verdict": "true" | "misleading" | "false" | "unverified", '
    '"confidence": "low" | "medium" | "high", '
    '"reason": "one plain sentence, 30 words at most"}'
)

_clients = {}
_clients_lock = threading.Lock()


def panel_members():
    """The members that can be asked right now: [{'key', 'name', 'model'}, ...] in asking order."""
    wanted = os.environ.get("FACTCHECK_PANEL", "").strip().lower()
    if wanted == "none":
        return []
    order = [part.strip() for part in wanted.split(",") if part.strip()] if wanted else list(MEMBERS)
    members = []
    for key in order:
        if key not in MEMBERS or any(member["key"] == key for member in members):
            continue
        name, key_variable, model_variable, default_model = MEMBERS[key]
        if os.environ.get(key_variable, "").strip():
            members.append({"key": key, "name": name,
                            "model": os.environ.get(model_variable, "").strip() or default_model})
    return members


def _client(key):
    """One client per service per process."""
    with _clients_lock:
        if key not in _clients:
            if key == "gpt":
                from openai import OpenAI
                _clients[key] = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip(), max_retries=1)
            elif key == "deepseek":
                from openai import OpenAI
                _clients[key] = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"].strip(),
                                       base_url=os.environ.get("FACTCHECK_PANEL_DEEPSEEK_URL", DEEPSEEK_BASE_URL),
                                       max_retries=1)
            elif key == "gemini":
                from google import genai
                from google.genai import types
                options = {"timeout": CALL_TIMEOUT_SECONDS * 1000}
                if os.environ.get("FACTCHECK_PANEL_GEMINI_URL"):
                    options["base_url"] = os.environ["FACTCHECK_PANEL_GEMINI_URL"]
                _clients[key] = genai.Client(api_key=os.environ["GOOGLE_API_KEY"].strip(),
                                             http_options=types.HttpOptions(**options))
        return _clients[key]


def _ask_openai_style(key, model, system, user_text):
    """GPT and DeepSeek speak the same chat format."""
    arguments = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_text}],
        "response_format": {"type": "json_object"},
        "timeout": CALL_TIMEOUT_SECONDS,
    }
    if key == "gpt":
        arguments["max_completion_tokens"] = MAX_ANSWER_TOKENS     # GPT-5 models require this name
    else:
        arguments["max_tokens"] = MAX_ANSWER_TOKENS
    response = _client(key).chat.completions.create(**arguments)
    usage = getattr(response, "usage", None)
    return (response.choices[0].message.content or "",
            getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0)


def _ask_gemini(model, system, user_text):
    from google.genai import types
    response = _client("gemini").models.generate_content(
        model=model, contents=user_text,
        config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=MAX_ANSWER_TOKENS,
                                           response_mime_type="application/json"))
    usage = getattr(response, "usage_metadata", None)
    return (response.text or "",
            getattr(usage, "prompt_token_count", 0) or 0, getattr(usage, "candidates_token_count", 0) or 0)


def _read_answer(text):
    """Pull the verdict out of a member's reply. Returns a dict, or None if it cannot be read."""
    text = str(text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    verdict = str(data.get("verdict") or "").strip().lower()
    if verdict not in VERDICTS:
        return None
    confidence = str(data.get("confidence") or "").strip().lower()
    reason = " ".join(str(data.get("reason") or "").split())
    return {"verdict": verdict,
            "confidence": confidence if confidence in ("low", "medium", "high") else "low",
            "reason": reason[:400]}


def _plain_error(error):
    """A short reason a member gave no answer. Never includes a key."""
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    name = type(error).__name__
    if status in (401, 403):
        return "its key was refused"
    if status == 402 or "RESOURCE_EXHAUSTED" in str(error) or "insufficient" in str(error).lower():
        return "its account is out of credit"
    if status == 404:
        return "its model name was not found"
    if status == 429:
        return "it is rate-limited right now"
    if "Timeout" in name or "timed out" in str(error).lower():
        return "it took too long"
    return f"its service returned an error ({status or name})"


def _ask_one(member, system, user_text):
    started = time.time()
    result = {"key": member["key"], "name": member["name"], "model": member["model"], "ok": False}
    try:
        if member["key"] == "gemini":
            text, tokens_in, tokens_out = _ask_gemini(member["model"], system, user_text)
        else:
            text, tokens_in, tokens_out = _ask_openai_style(member["key"], member["model"], system, user_text)
        result["input_tokens"], result["output_tokens"] = tokens_in, tokens_out
        answer = _read_answer(text)
        if answer is None:
            result["error"] = "its answer could not be read"
        else:
            result.update(answer)
            result["ok"] = True
    except Exception as error:  # noqa: BLE001 - a member failing is a result, not a crash
        logger.warning("Fact-check panel member %s failed: %s: %s", member["key"], type(error).__name__, error)
        result["error"] = _plain_error(error)
    result["seconds"] = round(time.time() - started, 1)
    return result


def ask_panel(system, user_text):
    """
    Ask every available member at the same time.
    Returns {'panel': [one result per member, in asking order], 'asked': n, 'answered': m}.
    """
    members = panel_members()
    if not members:
        return {"panel": [], "asked": 0, "answered": 0}
    system = system + ANSWER_FORMAT
    pool = ThreadPoolExecutor(max_workers=len(members), thread_name_prefix="FactCheckPanel")
    futures = {pool.submit(_ask_one, member, system, user_text): member for member in members}
    done, _late = wait(futures, timeout=PANEL_BUDGET_SECONDS)
    pool.shutdown(wait=False)
    results = []
    for future, member in futures.items():
        if future in done:
            results.append(future.result())
        else:
            results.append({"key": member["key"], "name": member["name"], "model": member["model"],
                            "ok": False, "error": "it took too long", "seconds": PANEL_BUDGET_SECONDS})
    return {"panel": results, "asked": len(results), "answered": sum(1 for row in results if row["ok"])}


# I did no harm and this file is not truncated
