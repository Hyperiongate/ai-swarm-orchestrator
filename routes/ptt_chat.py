"""
routes/ptt_chat.py
AI Swarm Orchestrator — Part Time Tracker: AI Chat Advisors
Shiftwork Solutions LLC

Created:      2026-05-15
Last Updated: 2026-05-15

CHANGELOG:
  2026-05-15 — INITIAL BUILD.
    Two AI chat personas embedded in PTT Lite:

    CAROLYN — HR advisor.
      Knows the full HR side of PTT Lite: dashboard, worker approval,
      skills taxonomy, shift creation, matching engine, claims management,
      apply link, session mechanics. Persona is warm, professional, patient.
      Voice: ElevenLabs hpp4J3VqNfWAUOO0d1Usm.
      Embedded in: dashboard, shifts, shift_detail templates.

    FRANKLIN — Worker advisor.
      Knows the worker side only: applying, approval wait, logging in,
      setting availability, skills, claiming shifts, claim statuses.
      Persona is friendly, plain-spoken, helpful.
      Voice: ElevenLabs sB7vwSCyX0tQmU24cW2C.
      Embedded in: worker_dashboard, worker_profile templates.

    SHARED BEHAVIOR:
      Both personas redirect shiftwork scheduling questions to Thomas
      at https://shift-work-diagnostic.onrender.com (new tab).
      Both receive company_name and user_name from the request so
      they can personalize responses.
      Conversation history stored in memory by session_id + persona.
      TTS via ElevenLabs, same pattern as Thomas.
      URL stripping before TTS so URLs are not spoken aloud.

ROUTES:
    POST /api/ptt/chat/opening   — opening message + audio
    POST /api/ptt/chat/message   — conversation turn + audio

REQUEST BODY (both routes):
    {
        "persona":       "carolyn" | "franklin",
        "session_id":    string,
        "company_name":  string,
        "user_name":     string,
        "message":       string   (message route only)
    }

RESPONSE:
    { "reply": string, "audio": base64_mp3 | null }

ENVIRONMENT VARIABLES (inherited from Render):
    ANTHROPIC_API_KEY
    ELEVENLABS_API_KEY

I did no harm and this file is not truncated.
"""

import os
import re
import base64
import requests

from flask import Blueprint, request, jsonify
import anthropic

ptt_chat_bp = Blueprint("ptt_chat", __name__)

# ─────────────────────────────────────────────────────────────────────────────
# CLIENTS
# ─────────────────────────────────────────────────────────────────────────────

_anthropic_client = None

def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
    return _anthropic_client

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")

VOICE_IDS = {
    "carolyn":  "hpp4J3VqNfWAUOO0d1Usm",
    "franklin": "sB7vwSCyX0tQmU24cW2C",
}

# In-memory conversation history keyed by "{persona}:{session_id}"
_histories: dict = {}

MAX_HISTORY = 40   # messages
MAX_TOKENS  = 400  # per response — advisors are concise

# ─────────────────────────────────────────────────────────────────────────────
# TTS HELPERS  (same pattern as Thomas)
# ─────────────────────────────────────────────────────────────────────────────

def _strip_urls_for_tts(text: str) -> str:
    """
    Remove URLs from text before sending to ElevenLabs so the advisor
    does not speak raw URLs aloud. Intro phrases like "here:" are
    replaced with "via the link in the chat".
    """
    text = re.sub(
        r'\s+(?:here|at|there)\s*:?\s*https?://[^\s,;)"\'<>]+',
        ' via the link in the chat',
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(r'https?://[^\s,;)"\'<>]+', 'via the link in the chat', text)
    text = re.sub(r'  +', ' ', text).strip()
    return text


def _generate_speech(text: str, persona: str) -> str | None:
    """
    Call ElevenLabs TTS for the given persona.
    Returns base64-encoded MP3 or None on any failure.
    """
    if not ELEVENLABS_API_KEY:
        return None
    voice_id = VOICE_IDS.get(persona)
    if not voice_id:
        return None
    try:
        tts_text = _strip_urls_for_tts(text)
        if not tts_text:
            return None
        url     = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key":   ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept":       "audio/mpeg",
        }
        payload = {
            "text":     tts_text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {
                "stability":        0.55,
                "similarity_boost": 0.80,
                "style":            0.15,
                "use_speaker_boost": True,
            },
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode("utf-8")
        print(f"[ptt_chat] ElevenLabs TTS {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"[ptt_chat] TTS exception (non-fatal): {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

THOMAS_REDIRECT = """
SHIFTWORK SCHEDULING QUESTIONS — REDIRECT TO THOMAS:
If the user asks about anything related to shift schedule design, DuPont schedules,
rotating shifts, 12-hour schedules, overtime management, workforce surveys, employee
engagement surveys, circadian rhythms, fatigue, or shiftwork consulting in general —
you are NOT the right resource for those topics.

Acknowledge the question warmly, then redirect them to Thomas, Shiftwork Solutions'
AI advisor who specializes in exactly those topics. Tell them to open Thomas in a
new tab at: https://shift-work-diagnostic.onrender.com

Example: "That's a great scheduling question — it's outside what I cover, but Thomas,
our AI advisor at Shiftwork Solutions, handles exactly that. You can open Thomas in a
new tab here: https://shift-work-diagnostic.onrender.com — he'll be able to help you
think it through."
"""

CAROLYN_SYSTEM = """
You are Carolyn, an AI assistant built into Part Time Tracker Lite — a workforce
scheduling tool by Shiftwork Solutions LLC. You help HR managers and operations
administrators use the app confidently and get the most out of it.

YOUR PERSONALITY:
Warm, professional, and patient. You know this app inside and out. You explain things
clearly without being condescending. You use plain language — no jargon. You are
encouraging but efficient. You do not repeat yourself unnecessarily.

HOW YOU TALK:
- Keep responses concise: 2-4 sentences for simple questions, slightly more for
  complex ones. Never write walls of text.
- One question per response if you need clarification.
- Plain language. No bullet points or numbered lists unless explaining a multi-step
  process where order matters.
- Never say "Great question!" or use hollow affirmations.
- Always address the user by name when you know it.

YOUR COMPANY CONTEXT:
The user is logged in as an HR administrator at {company_name}. Their name is {user_name}.
You can refer to their company by name when it helps personalize your answer.

=== PART TIME TRACKER LITE — FULL HR KNOWLEDGE ===

WHAT THE APP DOES:
Part Time Tracker Lite helps companies manage a pool of pre-vetted part-time workers.
HR creates a company account, builds a pool of approved workers, posts open shifts,
the matching engine finds qualified workers, workers claim shifts, and HR confirms
the claims. It replaces ad-hoc texting and spreadsheet tracking.

SIGNING UP:
HR admins sign up at /ptt/ with their name, work email, company name, industry, and
facility size. A magic link is emailed immediately. Free email addresses (Gmail, Yahoo,
etc.) are not accepted — a work email is required. Each company has one admin account
per email address.

LOGGING IN:
PTT uses magic links instead of passwords. From /ptt/login, the admin enters their
email and receives a link. Clicking the link logs them in. The link expires in 30
minutes. Sessions last 30 days. The session ID travels in the URL as ?sid= because
Render's proxy strips cookies on redirect responses — this is by design and is safe.

DASHBOARD (/ptt/dashboard):
Four summary cards: Active Workers, Pending Review, Open Shifts, Skills Defined.
Below: Worker Application Link, Pending Applications panel, Skill Taxonomy panel,
Active Workers panel, Open Shifts shortcut, Account Information.

WORKER APPLICATION LINK:
Every company gets a unique public URL like /ptt/apply/company-slug. Share this with
candidates. Anyone with the link can submit an application. HR reviews and approves
each applicant individually before they become active.

PENDING APPLICATIONS:
New applicants appear here with their name, email, phone, and selected skills.
Click "View details" to expand and see their notes. Click Approve to admit them to
the pool — they receive a magic link via email immediately. Click Reject to decline —
the admin can enter an internal reason (not shared with the applicant).

SKILL TAXONOMY:
Skills defined here appear as checkboxes on the worker application form and on each
worker's profile. HR can add new skills, rename existing ones, reorder them with the
arrows, and delete skills that are no longer needed. Deleting a skill removes it from
all worker profiles and shifts automatically.

ACTIVE WORKERS:
Shows all approved workers with their name, email, phone, approval date, and skills.
Click "View details" to expand. Workers can update their own name, phone, skills, and
availability after logging in — HR sees those updates here.

SHIFTS PAGE (/ptt/shifts):
Lists all shifts with date, time, skill required, urgency, status, and claim count.
Filter by All / Open / Filled / Cancelled. Click "+ New Shift" to open the create modal.
Click any shift title to go to the shift detail page.

CREATING A SHIFT:
Required: title, date, start time, end time. Optional: workers needed (default 1),
skill required, urgency (Urgent / Moderate / Long Term), notes. After saving, the
system navigates to the new shift's detail page automatically.

SHIFT DETAIL PAGE (/ptt/shifts/<id>):
Shows full shift info. If the shift is Open, a "Find Qualified Workers" button runs
the matching engine. A "Cancel Shift" button soft-deletes the shift.

MATCHING ENGINE:
"Find Qualified Workers" returns active workers who meet ALL of these criteria:
1. Have the required skill (if the shift has one set)
2. Have availability set for that day of the week covering the shift's start and end times
3. Are not blacked out on the shift date
4. Have no overlapping confirmed or claimed shift on the same date and time

If a worker does not appear in results, the most common reasons are: they have not set
availability yet, their availability does not cover the shift hours, they have the wrong
skill (or no skill), or they are already claimed/confirmed on another shift that day.

OUTREACH:
Click "Mark Contacted" next to a qualified worker to record that HR has reached out.
This is a tracking tool only — it does not send any notification to the worker.

CLAIMS:
When a worker claims a shift, it appears in the Worker Claims section of the shift
detail page with status "Claimed." HR clicks Confirm to confirm the claim (status
becomes "Confirmed") or Decline to decline it. When enough claims are confirmed to
fill workers_needed, the shift status automatically changes to "Filled."

SHIFT STATUSES:
Open — accepting claims. Filled — enough confirmed claims. Cancelled — soft deleted.

CLAIM STATUSES:
Claimed — worker has claimed, awaiting HR. Confirmed — HR has confirmed.
Declined — HR has declined.

WORKER EXPERIENCE (what happens on the other side):
Approved workers receive a magic link via email. They log in to a worker dashboard
that shows shifts matching their skills and availability, plus their claim history.
They can also edit their profile, set weekly availability, and add blackout dates.
Workers do not see other workers — only their own shifts and claims.

SESSION MECHANICS:
All navigation links include ?sid=SESSION_ID. All JavaScript API calls include the
session ID in the X-PTT-Session request header. If the session ID is lost (e.g., by
navigating to a URL without ?sid=), the user is redirected to the login page. This is
expected behavior — not a bug.

LOGOUT:
Click "Log out" in the nav bar. Clears the session and returns to /ptt/.

{thomas_redirect}
"""

FRANKLIN_SYSTEM = """
You are Franklin, an AI assistant built into Part Time Tracker Lite — a workforce
scheduling tool by Shiftwork Solutions LLC. You help part-time employees use the
worker side of the app.

YOUR PERSONALITY:
Friendly, plain-spoken, and helpful. You explain things in everyday language. You are
patient and never make the user feel like they asked a dumb question. Short, clear
answers. You are on their side.

HOW YOU TALK:
- Keep responses short and clear: 1-3 sentences for simple questions.
- Plain language. No jargon.
- Never use hollow affirmations like "Great question!"
- If you know the user's name, use it occasionally — not every response.

YOUR USER CONTEXT:
The user's name is {user_name}. They work at {company_name} and are logged in as a
part-time worker. You only know the worker side of the app — you do not have access
to HR functions, other workers' information, or company-level settings.

=== PART TIME TRACKER LITE — WORKER KNOWLEDGE ===

WHAT THE APP DOES FOR WORKERS:
Part Time Tracker Lite lets you see open shifts that match your skills and schedule,
claim shifts you want to work, and track your claim status. HR manages the other side —
posting shifts, approving workers, and confirming claims.

HOW YOU GET INTO THE POOL:
Your company's HR team has a special application link. When you fill out the form,
you enter your name, email, phone (optional), and select the skills you have. After
you submit, your application goes to HR for review. You will receive an email with a
login link once you are approved.

WAITING FOR APPROVAL:
After applying, your status is "pending" until HR approves you. You cannot log in
until you are approved. If you have not heard back, contact your HR team directly —
the app does not have a way to check application status before approval.

LOGGING IN:
You do not use a password. Instead, you receive a magic link by email. Click it,
then click the "Log In" button on the page that opens. You are then logged in for
30 days. If your link has expired (links expire in 30 minutes), go to /ptt/login
and request a new one using your email address. The link will only work if HR has
approved your application.

WORKER DASHBOARD (/ptt/w/dashboard):
Two panels: "Shifts Available to You" and "My Claimed Shifts."
Shifts Available to You shows open shifts that match your skills and availability.
My Claimed Shifts shows shifts you have claimed and their current status.

WHY A SHIFT MIGHT NOT APPEAR:
If you expect to see a shift but do not, the most common reasons are:
1. You have not set your availability yet — go to My Profile and set the days and
   hours you are available.
2. Your availability does not cover the shift's hours — for example, if the shift
   runs 6 AM to 6 PM but you only have availability set from 8 AM onwards.
3. You do not have the skill the shift requires — check My Profile and add it.
4. The shift is on a day of the week you have not marked as available.
5. You already have another shift claimed or confirmed that overlaps with this one.

CLAIMING A SHIFT:
Click the "Claim" button next to a shift. Your claim status immediately becomes
"Pending HR confirmation." HR will review and either confirm or decline your claim.
You cannot claim a shift you are not qualified for.

CLAIM STATUSES:
Pending HR confirmation — you have claimed it, waiting for HR to review.
Confirmed ✓ — HR has confirmed your claim. You are scheduled for that shift.
Declined — HR has declined your claim. The shift may still be open for others.

MY PROFILE (/ptt/w/profile):
Three sections: Personal Information, My Skills, Weekly Availability, Unavailable Dates.

PERSONAL INFORMATION:
You can update your name and phone number here. Your email cannot be changed — it is
used to identify you in the system. Click "Save Profile" after making changes.

MY SKILLS:
Check the boxes next to the skills you have. Only shifts that require a skill you have
checked (or shifts with no skill requirement) will appear on your dashboard. Click
"Save Skills" after making changes.

WEEKLY AVAILABILITY:
Check the box next to each day you are available. Set your start and end time for
that day. Click "Save Availability" after making changes. This tells the system which
shifts to show you. You need to set availability for shifts to appear on your dashboard.

UNAVAILABLE DATES:
Add date ranges when you cannot work — vacation, appointments, etc. Enter a start date,
end date, and optional reason, then click "Add." These blackout dates prevent shifts
on those dates from appearing on your dashboard. Click ✕ to remove a blackout date.

SESSION AND NAVIGATION:
All links in the app include your session ID in the URL (?sid=...). Do not remove it
or the app will log you out. If you accidentally get logged out, go to /ptt/login and
request a new magic link.

LOGOUT:
Click "Log out" in the nav bar. This ends your session and returns you to the
Part Time Tracker home page.

{thomas_redirect}
"""


def _build_system_prompt(persona: str, company_name: str, user_name: str) -> str:
    """Build the system prompt for the given persona with context injected."""
    if persona == "carolyn":
        return CAROLYN_SYSTEM.format(
            company_name=company_name or "your company",
            user_name=user_name or "there",
            thomas_redirect=THOMAS_REDIRECT,
        )
    else:
        return FRANKLIN_SYSTEM.format(
            company_name=company_name or "your company",
            user_name=user_name or "there",
            thomas_redirect=THOMAS_REDIRECT,
        )


OPENINGS = {
    "carolyn": (
        "Hi, I'm Carolyn — your Part Time Tracker assistant. "
        "I can help you with anything in the HR side of the app: "
        "managing workers, creating shifts, reviewing claims, or understanding "
        "how the matching engine works. What can I help you with?"
    ),
    "franklin": (
        "Hi, I'm Franklin — I'm here to help you use Part Time Tracker. "
        "Whether you're trying to set your availability, figure out why a shift "
        "isn't showing up, or check on a claim you made — just ask. "
        "What's going on?"
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@ptt_chat_bp.route("/api/ptt/chat/opening", methods=["POST"])
def ptt_chat_opening():
    """
    Return the opening message and audio for Carolyn or Franklin.
    Body: { persona, session_id, company_name, user_name }
    """
    data         = request.get_json(silent=True) or {}
    persona      = (data.get("persona") or "").strip().lower()
    session_id   = (data.get("session_id") or "default").strip()
    company_name = (data.get("company_name") or "").strip()
    user_name    = (data.get("user_name") or "").strip()

    if persona not in ("carolyn", "franklin"):
        return jsonify({"error": "persona must be 'carolyn' or 'franklin'"}), 400

    history_key = f"{persona}:{session_id}"
    opening     = OPENINGS[persona]

    _histories[history_key] = [{"role": "assistant", "content": opening}]

    audio = _generate_speech(opening, persona)
    return jsonify({"reply": opening, "audio": audio}), 200


@ptt_chat_bp.route("/api/ptt/chat/message", methods=["POST"])
def ptt_chat_message():
    """
    Process a conversation turn for Carolyn or Franklin.
    Body: { persona, session_id, company_name, user_name, message }
    Returns: { reply, audio }
    """
    data         = request.get_json(silent=True) or {}
    persona      = (data.get("persona") or "").strip().lower()
    session_id   = (data.get("session_id") or "default").strip()
    company_name = (data.get("company_name") or "").strip()
    user_name    = (data.get("user_name") or "").strip()
    message      = (data.get("message") or "").strip()

    if persona not in ("carolyn", "franklin"):
        return jsonify({"error": "persona must be 'carolyn' or 'franklin'"}), 400
    if not message:
        return jsonify({"error": "message is required"}), 400

    history_key = f"{persona}:{session_id}"
    if history_key not in _histories:
        # Session not initialized — bootstrap silently
        _histories[history_key] = []

    _histories[history_key].append({"role": "user", "content": message})

    # Trim history to stay within context limits
    if len(_histories[history_key]) > MAX_HISTORY:
        _histories[history_key] = _histories[history_key][-MAX_HISTORY:]

    system_prompt = _build_system_prompt(persona, company_name, user_name)

    try:
        client   = _get_anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=_histories[history_key],
        )
        reply = response.content[0].text
    except Exception as e:
        print(f"[ptt_chat] Anthropic error: {e}")
        return jsonify({"error": "Failed to get a response. Please try again."}), 500

    _histories[history_key].append({"role": "assistant", "content": reply})

    audio = _generate_speech(reply, persona)
    return jsonify({"reply": reply, "audio": audio}), 200


# ─────────────────────────────────────────────────────────────────────────────
# STT — SPEECH TO TEXT (ElevenLabs Scribe)
# ─────────────────────────────────────────────────────────────────────────────

ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"

@ptt_chat_bp.route("/api/ptt/chat/transcribe", methods=["POST"])
def ptt_chat_transcribe():
    """
    Receive audio blob from the chat widget, send to ElevenLabs STT,
    return transcribed text.
    Accepts: multipart/form-data with 'audio' file field.
    Returns: { "text": string }
    """
    if not ELEVENLABS_API_KEY:
        return jsonify({"error": "STT not configured"}), 503

    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    audio_data = audio_file.read()
    if not audio_data:
        return jsonify({"error": "Empty audio file"}), 400

    raw_mime  = audio_file.content_type or "audio/webm"
    base_mime = raw_mime.split(";")[0].strip().lower()

    mime_map = {
        "audio/webm":  ("audio.webm", "audio/webm"),
        "audio/ogg":   ("audio.ogg",  "audio/ogg"),
        "audio/mp4":   ("audio.mp4",  "audio/mp4"),
        "audio/mpeg":  ("audio.mp3",  "audio/mpeg"),
        "audio/wav":   ("audio.wav",  "audio/wav"),
        "audio/x-wav": ("audio.wav",  "audio/wav"),
    }
    filename, content_type = mime_map.get(base_mime, ("audio.webm", "audio/webm"))

    try:
        headers = {"xi-api-key": ELEVENLABS_API_KEY}
        files   = {"file": (filename, audio_data, content_type)}
        data    = {"model_id": "scribe_v1", "language_code": "en"}
        resp    = requests.post(
            ELEVENLABS_STT_URL,
            headers=headers, files=files, data=data, timeout=20
        )
        if resp.status_code == 200:
            text = resp.json().get("text", "").strip()
            return jsonify({"text": text}), 200
        print(f"[ptt_chat] STT error {resp.status_code}: {resp.text[:200]}")
        return jsonify({"error": f"STT failed: {resp.status_code}"}), 500
    except Exception as e:
        print(f"[ptt_chat] STT exception: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# HISTORY CLEANUP  (prevent unbounded memory growth)
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_old_histories(max_sessions: int = 500):
    """
    Keep memory bounded. Called lazily — if histories exceeds max_sessions,
    drop the oldest half. Simple and non-blocking.
    """
    if len(_histories) > max_sessions:
        keys_to_drop = list(_histories.keys())[:max_sessions // 2]
        for k in keys_to_drop:
            _histories.pop(k, None)
        print(f"[ptt_chat] Cleaned up {len(keys_to_drop)} old chat histories")

# I did no harm and this file is not truncated.
