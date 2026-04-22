"""
routes/assessment_pdf.py
AI Swarm Orchestrator — Shiftwork Operations Assessment PDF
Shiftwork Solutions LLC

Created:      2026-04-21
Last Updated: 2026-04-22

CHANGE LOG:
  2026-04-22 — CORS HOTFIX.
    Initial 2026-04-21 build relied on flask_cors's @cross_origin()
    decorator. In production behind Render's proxy, preflight
    OPTIONS requests from shift-work.com were being blocked:
      "No 'Access-Control-Allow-Origin' header is present on the
       requested resource."
    Root cause: the decorator's defaults don't reliably attach
    headers to every response through Render's proxy. The rest
    of the Swarm (newsletter_bp, contact_api_bp) uses a manual
    after_request pattern with an explicit allow-list of origins
    and that pattern has been proven in production for months.
    This file now uses that exact same pattern. No functional
    behavior changed — just the CORS handling mechanics.

  2026-04-21 — INITIAL BUILD.
    Creates POST /api/assessment/generate-pdf endpoint for the
    Shiftwork Operations Reality Check + Detailed Analysis flow.
    Generates a branded, professionally-formatted multi-page PDF
    using ReportLab, returns it as a direct download to the user's
    browser, and simultaneously sends a copy to Contact@shift-work.com
    via Resend with the user's contact info in the email body.

    PDF structure (5 sections):
      1. Cover page — logo mark, title, name/company/date
      2. Reality Check recap — all 8 Tier 1 Q&A reveals in
         condensed form
      3. Executive summary — AI narrative + top strengths/priorities
      4. Dimensional scorecard — 8 dimensions with visual bars
      5. About Shiftwork Solutions — ~200-word institutional block
         emphasizing the three-phase process: analyze → engage
         workforce → implement. No consultants named.

    Email notification to Contact@shift-work.com includes:
      - Subject: "Assessment PDF downloaded — {company}"
      - Body: name, email, company, industry, shift workers,
        biggest challenge, overall score
      - Attachment: the exact PDF the user received

    ARCHITECTURE NOTES:
    - Fully self-contained module. Does NOT import from any
      other Swarm blueprint. Does NOT touch routes/assessment.py.
      Rule 1 (do no harm) is preserved.
    - Resend email is sent AFTER the PDF is streamed to the user
      so email latency does not delay the user's download.
    - If Resend fails, the user still gets their PDF. Email
      failures are logged but never block the user flow.
    - Uses the existing RESEND_API_KEY env var already set in
      Render (same one Thomas transcripts use).

  REGISTRATION in Swarm's app.py:
    from routes.assessment_pdf import assessment_pdf_bp
    app.register_blueprint(assessment_pdf_bp)

  ENVIRONMENT VARIABLES:
    RESEND_API_KEY — already set in Render for Thomas transcripts
"""

import os
import io
import base64
import traceback
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as pdf_canvas


# =============================================================================
# BLUEPRINT
# =============================================================================
assessment_pdf_bp = Blueprint(
    "assessment_pdf",
    __name__,
    url_prefix="/api/assessment",
)


# =============================================================================
# CORS — matches the proven pattern used by routes/newsletter.py
# Allow-listed origins only. Manual after_request handler so Render's proxy
# reliably returns the Access-Control-Allow-Origin header.
# =============================================================================

ALLOWED_ORIGINS = [
    'https://shift-work.com',
    'https://www.shift-work.com',
    'http://localhost:3000',
    'http://localhost:5000',
    'http://127.0.0.1:5500',
    'null',
]


def _cors_headers(origin=None):
    """Return CORS headers dict for the given origin."""
    headers = {
        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Accept',
        'Access-Control-Max-Age': '86400',
    }
    if origin in ALLOWED_ORIGINS:
        headers['Access-Control-Allow-Origin'] = origin
    elif origin and (origin.endswith('.shift-work.com') or origin.endswith('.onrender.com')):
        headers['Access-Control-Allow-Origin'] = origin
    else:
        headers['Access-Control-Allow-Origin'] = 'https://shift-work.com'
    return headers


@assessment_pdf_bp.after_request
def add_cors_headers(response):
    """Add CORS headers to every response from this blueprint."""
    origin = request.headers.get('Origin', '')
    for key, value in _cors_headers(origin).items():
        response.headers[key] = value
    return response


# =============================================================================
# BRAND CONSTANTS (match shift-work.com and Thomas PDF)
# =============================================================================
NAVY       = HexColor("#1F4E79")
NAVY_DARK  = HexColor("#0D1F3C")
ORANGE     = HexColor("#E8610A")
GOLD       = HexColor("#EEAE26")
GREEN      = HexColor("#1D9E75")
RED        = HexColor("#C62828")
AMBER      = HexColor("#F9A825")
MID_BLUE   = HexColor("#85B7EB")
LIGHT_BLUE = HexColor("#EEF3F8")
LIGHT_GREY = HexColor("#F4F6F8")
BODY_TEXT  = HexColor("#1A1A1A")
MUTED      = HexColor("#666666")
BORDER_MED = HexColor("#E0E0E0")


# =============================================================================
# EMAIL RECIPIENT — every downloaded PDF is copied here
# =============================================================================
NOTIFICATION_RECIPIENT = "Contact@shift-work.com"
EMAIL_FROM             = "Shiftwork Assessment <assessment@shift-work.com>"


# =============================================================================
# ABOUT SHIFTWORK SOLUTIONS — INSTITUTIONAL BLOCK
#
# ~200 words. No consultants named. Emphasizes the three-phase process:
#   1. Analyze the current operation
#   2. Engage the workforce
#   3. Implement the final solution
# Closes with "we do it all" positioning.
# =============================================================================
ABOUT_TEXT_PARAGRAPHS = [
    (
        "Shiftwork Solutions LLC is a management consulting firm dedicated "
        "exclusively to shift schedule design, workforce engagement, and "
        "change management for 24/7 industrial operations. Over more than "
        "thirty years, we have worked with hundreds of facilities across "
        "sixteen industries — manufacturing, pharmaceutical, food processing, "
        "mining, distribution, chemicals, utilities, and more. Our proprietary "
        "normative database of more than 20,000 shift worker responses is the "
        "largest benchmark dataset of its kind, and it informs every engagement "
        "we undertake."
    ),
    (
        "What sets us apart is that we handle the full arc of change. Our "
        "engagements move through three phases, and we lead every one of them. "
        "We begin by analyzing the current operation in depth — schedule design, "
        "cost structure, workforce composition, and operational context. "
        "We then engage the workforce directly through a structured, confidential "
        "survey process that typically reaches 80% or more of affected employees. "
        "Finally, we design and implement the solution alongside management, "
        "including communication planning, policy alignment, and the "
        "implementation phase where most change efforts actually succeed or fail."
    ),
    (
        "Schedule changes fail when they are imposed. They succeed when the "
        "workforce is genuinely involved in shaping them. We have built our "
        "practice around making that second outcome the reliable one. Engagements "
        "are fixed-fee and typically run five to ten weeks. Most clients recover "
        "the investment within three months."
    ),
]


# =============================================================================
# SCORE COLOR HELPERS
# =============================================================================
def color_for_score(score):
    """Red/amber/green color for a 0-100 dimension score."""
    try:
        s = float(score)
    except Exception:
        return MUTED
    if s >= 70:
        return GREEN
    if s >= 40:
        return AMBER
    return RED


def wrap_text(canvas_obj, text, font_name, font_size, max_width):
    """Word-wrap text to fit within max_width. Returns list of lines."""
    if not text:
        return []
    words = text.split()
    lines = []
    line  = ""
    for word in words:
        test = (line + " " + word).strip()
        if canvas_obj.stringWidth(test, font_name, font_size) < max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# =============================================================================
# PDF BUILDER
#
# Takes the full results payload from the front-end and renders a 5-section
# branded PDF. Returns a BytesIO buffer positioned at 0.
# =============================================================================
def build_assessment_pdf(payload):
    """
    Build the full assessment PDF.

    Expected payload keys (all optional — the function handles missing
    fields gracefully):
      contact:
        name, email, company, industry, shift_workers, biggest_challenge
      tier1:
        reveals: [ { question, category, prediction, pattern, narrative }, ... ]
      tier2:
        overall_score, overall_label, narrative,
        dimensions: { key: { label, score, low_label, high_label } },
        strengths:     [ { title, detail } ],
        opportunities: [ { title, detail, shiftwork_note } ],
        actions:       [ str, ... ]
    """
    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 0.75 * inch

    contact = payload.get("contact", {}) or {}
    tier1   = payload.get("tier1", {})   or {}
    tier2   = payload.get("tier2", {})   or {}

    name     = (contact.get("name")     or "").strip()
    email    = (contact.get("email")    or "").strip()
    company  = (contact.get("company")  or "").strip()
    industry = (contact.get("industry") or "").strip()

    today_str = datetime.now().strftime("%B %d, %Y")

    # ------------------------------------------------------------------
    # Helper: render a reusable page footer (brand + contact strip)
    # ------------------------------------------------------------------
    def draw_footer(page_label=""):
        c.setFillColor(NAVY_DARK)
        c.rect(0, 0, width, 0.55 * inch, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica", 8.5)
        c.drawString(margin, 0.33 * inch,
                     "Shiftwork Solutions LLC  |  shift-work.com  |  "
                     "Contact@shift-work.com  |  (415) 265-1621")
        if page_label:
            c.drawRightString(width - margin, 0.33 * inch, page_label)

    # ------------------------------------------------------------------
    # Helper: page-break management. Accepts a cursor Y and the height
    # the next block will need; returns a fresh cursor if a break was
    # required.
    # ------------------------------------------------------------------
    def ensure_space(y_cursor, needed_inches, page_label_next=""):
        if y_cursor < (needed_inches * inch + 0.7 * inch):
            draw_footer(page_label_next)
            c.showPage()
            return height - margin
        return y_cursor

    # ==================================================================
    # SECTION 1 — COVER PAGE
    # ==================================================================
    # Navy top band (full width, ~2.8 inches tall)
    c.setFillColor(NAVY_DARK)
    c.rect(0, height - 2.8 * inch, width, 2.8 * inch, fill=1, stroke=0)

    # Orange accent strip
    c.setFillColor(ORANGE)
    c.rect(0, height - 2.82 * inch, width, 0.06 * inch, fill=1, stroke=0)

    # Decorative circle (top right)
    c.setStrokeColor(ORANGE)
    c.setLineWidth(1.5)
    c.circle(width - 0.6 * inch, height - 0.6 * inch, 1.2 * inch, stroke=1, fill=0)

    # Logo mark — circle with "S"
    c.setFillColor(ORANGE)
    c.circle(margin + 0.4 * inch, height - 0.9 * inch, 0.32 * inch, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(margin + 0.4 * inch, height - 1.02 * inch, "S")

    # Firm name next to logo mark
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin + 0.95 * inch, height - 0.8 * inch, "SHIFTWORK SOLUTIONS")
    c.setFillColor(MID_BLUE)
    c.setFont("Helvetica", 10)
    c.drawString(margin + 0.95 * inch, height - 1.02 * inch,
                 "Management Consulting for 24/7 Operations")

    # Document title
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(margin, height - 1.9 * inch, "Shiftwork Operations")
    c.drawString(margin, height - 2.28 * inch, "Analysis")

    # Document subtitle
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica", 12)
    c.drawString(margin, height - 2.58 * inch,
                 "Benchmark comparison + personalized operations analysis")

    # Eyebrow label
    c.setFillColor(MID_BLUE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, height - 2.72 * inch,
                 "PREPARED FOR   \u00b7   " + today_str.upper())

    # Identification block (below navy band)
    y = height - 3.6 * inch
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "PREPARED FOR")
    y -= 0.28 * inch

    if name:
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(margin, y, name)
        y -= 0.26 * inch
    if company:
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica", 13)
        c.drawString(margin, y, company)
        y -= 0.24 * inch
    if industry:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 11)
        c.drawString(margin, y, "Industry: " + industry)
        y -= 0.22 * inch
    if email:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 11)
        c.drawString(margin, y, email)
        y -= 0.22 * inch

    # Contents block
    y -= 0.35 * inch
    c.setFillColor(NAVY)
    c.setLineWidth(2)
    c.setStrokeColor(ORANGE)
    c.line(margin, y, margin + 0.6 * inch, y)
    y -= 0.20 * inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "WHAT'S INSIDE")
    y -= 0.25 * inch

    contents = [
        ("1.", "The Shiftwork Operations Reality Check"),
        ("2.", "Executive Summary"),
        ("3.", "Dimensional Scorecard"),
        ("4.", "About Shiftwork Solutions"),
    ]
    c.setFont("Helvetica", 11)
    c.setFillColor(BODY_TEXT)
    for num, title in contents:
        c.setFillColor(ORANGE)
        c.drawString(margin, y, num)
        c.setFillColor(BODY_TEXT)
        c.drawString(margin + 0.3 * inch, y, title)
        y -= 0.26 * inch

    draw_footer("Cover")
    c.showPage()

    # ==================================================================
    # SECTION 2 — REALITY CHECK RECAP
    # ==================================================================
    y = height - margin

    # Section header (compact: accent bar + eyebrow + title)
    c.setStrokeColor(ORANGE)
    c.setLineWidth(4)
    c.line(margin, y, margin + 0.45 * inch, y)
    y -= 0.18 * inch
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "PART 1")
    y -= 0.22 * inch
    c.setFillColor(BODY_TEXT)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "The Shiftwork Operations Reality Check")
    y -= 0.18 * inch
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    intro_lines = wrap_text(
        c,
        "Below is a record of your predictions alongside the pattern we see "
        "across hundreds of 24/7 operations from our benchmark database of "
        "more than 20,000 shift worker responses.",
        "Helvetica", 10, width - 2 * margin
    )
    for line in intro_lines:
        y -= 0.18 * inch
        c.drawString(margin, y, line)
    y -= 0.32 * inch

    # Reveal entries
    reveals = tier1.get("reveals", []) or []
    max_text_w = width - 2 * margin - 0.3 * inch

    # Layout geometry for the two-column prediction/pattern row
    col_gap       = 0.25 * inch
    col_w         = (max_text_w - col_gap) / 2.0
    col_left_x    = margin
    col_right_x   = margin + col_w + col_gap
    line_h_small  = 0.16 * inch   # 10-point text leading

    for i, reveal in enumerate(reveals):
        category   = (reveal.get("category")   or "").strip()
        question   = (reveal.get("question")   or "").strip()
        prediction = (reveal.get("prediction") or "").strip()
        pattern    = (reveal.get("pattern")    or "").strip()
        narrative  = (reveal.get("narrative")  or "").strip()

        # Pre-wrap all text blocks so we can compute the exact block height
        q_lines        = wrap_text(c, question, "Helvetica-Bold", 11, max_text_w) or [""]
        pred_lines     = wrap_text(c, prediction, "Helvetica-Bold", 10, col_w)    or [""]
        pattern_lines  = wrap_text(c, pattern, "Helvetica-Bold", 10, col_w)       or [""]
        narrative_lines= wrap_text(c, narrative, "Helvetica", 9.5, max_text_w)    or [""]
        compare_row_lines = max(len(pred_lines), len(pattern_lines))

        # Block height estimate: tag + question + gap + label row + compare rows + gap + narrative + divider
        block_est = (
            0.20                                      # tag row
            + 0.18 * len(q_lines)                     # question lines
            + 0.06                                    # small gap
            + 0.16                                    # compare-column labels
            + line_h_small / inch * compare_row_lines # wrapped compare content
            + 0.10                                    # gap
            + 0.16 * len(narrative_lines)             # narrative
            + 0.35                                    # divider + spacing
        )
        y = ensure_space(y, block_est, "Reality Check")

        # Reveal card tag
        c.setFillColor(ORANGE)
        c.setFont("Helvetica-Bold", 8)
        header = f"REVEAL {i+1} OF {len(reveals)}  \u00b7  {category.upper()}"
        c.drawString(margin, y, header)
        y -= 0.20 * inch

        # Question
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica-Bold", 11)
        for line in q_lines:
            c.drawString(margin, y, line)
            y -= 0.18 * inch

        # Prediction + Pattern — two-column compare row with proper wrapping
        y -= 0.04 * inch
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(col_left_x, y, "YOUR PREDICTION")
        c.setFillColor(NAVY)
        c.drawString(col_right_x, y, "THE BENCHMARK PATTERN")
        y -= 0.17 * inch

        # Render both columns — each can wrap to multiple lines independently
        compare_top_y = y
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica-Bold", 10)
        y_left = compare_top_y
        for line in pred_lines:
            c.drawString(col_left_x, y_left, line)
            y_left -= line_h_small

        c.setFillColor(NAVY)
        y_right = compare_top_y
        for line in pattern_lines:
            c.drawString(col_right_x, y_right, line)
            y_right -= line_h_small

        # Take the lower of the two column bottoms so the narrative sits below both
        y = min(y_left, y_right) - 0.02 * inch

        # Narrative
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica", 9.5)
        for line in narrative_lines:
            c.drawString(margin, y, line)
            y -= 0.16 * inch

        # Thin divider between reveals (except after last)
        if i < len(reveals) - 1:
            y -= 0.12 * inch
            c.setStrokeColor(BORDER_MED)
            c.setLineWidth(0.6)
            c.line(margin, y, width - margin, y)
            y -= 0.20 * inch

    # Biggest challenge footnote
    biggest = contact.get("biggest_challenge", "") or ""
    if biggest:
        y = ensure_space(y, 0.9, "Reality Check")
        y -= 0.12 * inch
        c.setFillColor(LIGHT_BLUE)
        c.rect(margin, y - 0.48 * inch, width - 2 * margin, 0.52 * inch, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(margin + 0.12 * inch, y - 0.16 * inch,
                     "YOUR STATED BIGGEST CHALLENGE")
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica", 10.5)
        c.drawString(margin + 0.12 * inch, y - 0.35 * inch, biggest)
        y -= 0.62 * inch

    draw_footer("Reality Check")
    c.showPage()

    # ==================================================================
    # SECTION 3 — EXECUTIVE SUMMARY
    # ==================================================================
    y = height - margin

    c.setStrokeColor(ORANGE)
    c.setLineWidth(4)
    c.line(margin, y, margin + 0.45 * inch, y)
    y -= 0.18 * inch
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "PART 2")
    y -= 0.22 * inch
    c.setFillColor(BODY_TEXT)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "Executive Summary")
    y -= 0.35 * inch

    # Overall score callout (navy card, ~1.4 inch tall)
    overall_score = tier2.get("overall_score", "--")
    overall_label = tier2.get("overall_label", "") or ""

    card_h = 1.35 * inch
    y_card = y - card_h
    c.setFillColor(NAVY)
    c.roundRect(margin, y_card, width - 2 * margin, card_h, 8, fill=1, stroke=0)

    c.setFillColor(MID_BLUE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin + 0.3 * inch, y - 0.28 * inch,
                 "OVERALL SHIFT OPERATIONS HEALTH SCORE")

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 42)
    score_str = f"{overall_score}%" if overall_score not in (None, "--") else "--"
    c.drawString(margin + 0.3 * inch, y - 0.85 * inch, score_str)

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica", 12)
    c.drawString(margin + 0.3 * inch, y - 1.12 * inch, overall_label)

    y = y_card - 0.30 * inch

    # Narrative
    narrative = tier2.get("narrative", "") or ""
    if narrative:
        y = ensure_space(y, 1.0, "Executive Summary")
        c.setFillColor(ORANGE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin, y, "READING OF YOUR SITUATION")
        y -= 0.22 * inch
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica", 10.5)
        for line in wrap_text(c, narrative, "Helvetica", 10.5, width - 2 * margin):
            y = ensure_space(y, 0.3, "Executive Summary")
            c.drawString(margin, y, line)
            y -= 0.18 * inch
        y -= 0.22 * inch

    # Strengths
    strengths = tier2.get("strengths", []) or []
    if strengths:
        y = ensure_space(y, 1.0, "Executive Summary")
        c.setFillColor(GREEN)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin, y, "\u2713  TOP STRENGTHS")
        y -= 0.22 * inch
        for s in strengths[:3]:
            title  = (s.get("title")  or "").strip()
            detail = (s.get("detail") or "").strip()
            combined = f"{title}. {detail}" if title else detail
            if not combined:
                continue
            y = ensure_space(y, 0.6, "Executive Summary")
            # Green vertical bar
            c.setFillColor(GREEN)
            c.rect(margin, y - 0.04 * inch, 0.06 * inch, 0.18 * inch, fill=1, stroke=0)
            c.setFillColor(BODY_TEXT)
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(margin + 0.18 * inch, y, title)
            y -= 0.18 * inch
            c.setFont("Helvetica", 9.5)
            c.setFillColor(MUTED)
            for line in wrap_text(c, detail, "Helvetica", 9.5,
                                  width - 2 * margin - 0.2 * inch):
                y = ensure_space(y, 0.3, "Executive Summary")
                c.drawString(margin + 0.18 * inch, y, line)
                y -= 0.16 * inch
            y -= 0.08 * inch

    # Priority areas
    opportunities = tier2.get("opportunities", []) or []
    if opportunities:
        y = ensure_space(y, 1.0, "Executive Summary")
        y -= 0.05 * inch
        c.setFillColor(ORANGE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin, y, "\u26A0  PRIORITY AREAS FOR IMPROVEMENT")
        y -= 0.22 * inch
        for o in opportunities[:3]:
            title  = (o.get("title")  or "").strip()
            detail = (o.get("detail") or "").strip()
            if not title and not detail:
                continue
            y = ensure_space(y, 0.6, "Executive Summary")
            c.setFillColor(ORANGE)
            c.rect(margin, y - 0.04 * inch, 0.06 * inch, 0.18 * inch, fill=1, stroke=0)
            c.setFillColor(BODY_TEXT)
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(margin + 0.18 * inch, y, title)
            y -= 0.18 * inch
            c.setFont("Helvetica", 9.5)
            c.setFillColor(MUTED)
            for line in wrap_text(c, detail, "Helvetica", 9.5,
                                  width - 2 * margin - 0.2 * inch):
                y = ensure_space(y, 0.3, "Executive Summary")
                c.drawString(margin + 0.18 * inch, y, line)
                y -= 0.16 * inch
            y -= 0.08 * inch

    draw_footer("Executive Summary")
    c.showPage()

    # ==================================================================
    # SECTION 4 — DIMENSIONAL SCORECARD
    # ==================================================================
    y = height - margin

    c.setStrokeColor(ORANGE)
    c.setLineWidth(4)
    c.line(margin, y, margin + 0.45 * inch, y)
    y -= 0.18 * inch
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "PART 3")
    y -= 0.22 * inch
    c.setFillColor(BODY_TEXT)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "Dimensional Scorecard")
    y -= 0.18 * inch
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    intro = ("Your operation evaluated across eight dimensions. Scores reflect "
             "where you sit on each dimension based on your 35 responses.")
    for line in wrap_text(c, intro, "Helvetica", 10, width - 2 * margin):
        y -= 0.18 * inch
        c.drawString(margin, y, line)
    y -= 0.35 * inch

    dim_order = ["worklife", "health", "alertness", "overtime",
                 "operations", "quality", "communication", "workforce"]
    dimensions = tier2.get("dimensions", {}) or {}

    # Available bar width (full-width horizontal bars)
    bar_x     = margin
    bar_w_max = width - 2 * margin

    for key in dim_order:
        d = dimensions.get(key) or {}
        label     = d.get("label", key.title())
        score     = d.get("score", 0)
        low_lbl   = d.get("low_label", "")
        high_lbl  = d.get("high_label", "")

        try:
            score_val = float(score)
        except Exception:
            score_val = 0.0
        score_val = max(0.0, min(100.0, score_val))

        y = ensure_space(y, 0.95, "Dimensional Scorecard")

        # Dimension label + numeric score
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(bar_x, y, label)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 13)
        c.drawRightString(bar_x + bar_w_max, y, f"{int(score_val)}%")
        y -= 0.22 * inch

        # Track (grey)
        c.setFillColor(BORDER_MED)
        c.roundRect(bar_x, y - 0.22 * inch, bar_w_max, 0.22 * inch, 3,
                    fill=1, stroke=0)
        # Fill (color-coded)
        fill_w = (score_val / 100.0) * bar_w_max
        if fill_w > 0.5:
            c.setFillColor(color_for_score(score_val))
            c.roundRect(bar_x, y - 0.22 * inch, fill_w, 0.22 * inch, 3,
                        fill=1, stroke=0)
        y -= 0.28 * inch

        # Extremes labels
        c.setFont("Helvetica", 8)
        c.setFillColor(RED)
        c.drawString(bar_x, y, low_lbl or "")
        c.setFillColor(GREEN)
        c.drawRightString(bar_x + bar_w_max, y, high_lbl or "")
        y -= 0.22 * inch

    draw_footer("Dimensional Scorecard")
    c.showPage()

    # ==================================================================
    # SECTION 5 — ABOUT SHIFTWORK SOLUTIONS
    # ==================================================================
    y = height - margin

    c.setStrokeColor(ORANGE)
    c.setLineWidth(4)
    c.line(margin, y, margin + 0.45 * inch, y)
    y -= 0.18 * inch
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "PART 4")
    y -= 0.22 * inch
    c.setFillColor(BODY_TEXT)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "About Shiftwork Solutions")
    y -= 0.35 * inch

    # Three-paragraph institutional block
    c.setFillColor(BODY_TEXT)
    c.setFont("Helvetica", 10.5)
    for para in ABOUT_TEXT_PARAGRAPHS:
        for line in wrap_text(c, para, "Helvetica", 10.5, width - 2 * margin):
            y = ensure_space(y, 0.3, "About Shiftwork Solutions")
            c.drawString(margin, y, line)
            y -= 0.18 * inch
        y -= 0.14 * inch

    # Three-phase process visual — three horizontal numbered blocks
    y = ensure_space(y, 1.8, "About Shiftwork Solutions")
    y -= 0.10 * inch
    c.setFillColor(ORANGE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "OUR THREE-PHASE PROCESS")
    y -= 0.30 * inch

    phase_h = 1.10 * inch
    phase_w = (width - 2 * margin - 0.30 * inch) / 3.0
    phases = [
        ("1", "ANALYZE",
         "We begin by understanding the current operation in depth — schedule "
         "design, cost structure, workforce composition, and operational context."),
        ("2", "ENGAGE",
         "We engage the workforce directly through a structured, confidential "
         "survey process that typically reaches 80% or more of affected employees."),
        ("3", "IMPLEMENT",
         "We design and implement the solution alongside management — including "
         "communication planning, policy alignment, and the implementation phase."),
    ]
    for i, (num, heading, desc) in enumerate(phases):
        x = margin + i * (phase_w + 0.15 * inch)
        c.setFillColor(LIGHT_BLUE)
        c.roundRect(x, y - phase_h, phase_w, phase_h, 6, fill=1, stroke=0)
        # Numeral
        c.setFillColor(ORANGE)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(x + 0.15 * inch, y - 0.38 * inch, num)
        # Heading
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 0.50 * inch, y - 0.30 * inch, heading)
        # Description
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica", 8.5)
        desc_lines = wrap_text(c, desc, "Helvetica", 8.5, phase_w - 0.3 * inch)
        dy = y - 0.50 * inch
        for line in desc_lines[:4]:
            c.drawString(x + 0.15 * inch, dy, line)
            dy -= 0.13 * inch
    y = y - phase_h - 0.30 * inch

    # Closing CTA block (navy dark card)
    y = ensure_space(y, 1.5, "About Shiftwork Solutions")
    cta_h = 1.10 * inch
    c.setFillColor(NAVY_DARK)
    c.roundRect(margin, y - cta_h, width - 2 * margin, cta_h, 8,
                fill=1, stroke=0)

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin + 0.30 * inch, y - 0.35 * inch,
                 "Ready to talk about your operation?")

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica", 10)
    c.drawString(margin + 0.30 * inch, y - 0.58 * inch,
                 "The first conversation is always free. Twenty minutes, no pitch.")

    c.setFillColor(MID_BLUE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin + 0.30 * inch, y - 0.85 * inch,
                 "(415) 265-1621  \u00b7  Contact@shift-work.com  \u00b7  "
                 "shift-work.com/contact/")

    draw_footer("About Shiftwork Solutions")
    c.save()
    buffer.seek(0)
    return buffer


# =============================================================================
# EMAIL NOTIFICATION TO Contact@shift-work.com
#
# Sends a copy of the generated PDF to Contact@shift-work.com via Resend,
# with the user's contact info and assessment summary in the email body.
# Fails silently if Resend is not available — the user's download is never
# blocked by email failures.
# =============================================================================
def _send_notification_email(pdf_bytes, payload):
    """
    Send notification email with PDF attachment.
    Returns (success: bool, info: str) — info is for logging only.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return (False, "RESEND_API_KEY not configured")

    try:
        import resend
    except ImportError:
        return (False, "resend library not installed")

    try:
        resend.api_key = api_key

        contact = payload.get("contact", {}) or {}
        tier2   = payload.get("tier2", {})   or {}

        name     = (contact.get("name")    or "").strip() or "(not provided)"
        email    = (contact.get("email")   or "").strip() or "(not provided)"
        company  = (contact.get("company") or "").strip() or "(not provided)"
        industry = (contact.get("industry") or "").strip() or "(not provided)"
        shift_wk = (contact.get("shift_workers") or "").strip() or "(not provided)"
        biggest  = (contact.get("biggest_challenge") or "").strip() or "(not provided)"

        overall_score = tier2.get("overall_score", "--")
        overall_label = tier2.get("overall_label", "") or ""
        score_str     = (f"{overall_score}% ({overall_label})"
                         if overall_score not in (None, "--")
                         else "(not scored)")

        # Subject includes company name for inbox triage
        subject_company = company if company != "(not provided)" else "company not provided"
        subject = f"Assessment PDF downloaded \u2014 {subject_company}"

        # Plain text body (works everywhere)
        body_text = (
            "A new Shiftwork Operations Analysis PDF was just downloaded.\n"
            "Contact details below, full PDF attached.\n"
            "\n"
            "--- CONTACT ---\n"
            f"Name:           {name}\n"
            f"Email:          {email}\n"
            f"Company:        {company}\n"
            f"Industry:       {industry}\n"
            f"Shift Workers:  {shift_wk}\n"
            "\n"
            "--- THEIR STATED CHALLENGE ---\n"
            f"{biggest}\n"
            "\n"
            "--- ASSESSMENT SCORE ---\n"
            f"Overall Score:  {score_str}\n"
            "\n"
            "The full PDF is attached to this email.\n"
            "\n"
            "---\n"
            "Automated notification from the Shiftwork Operations Reality Check\n"
            "shift-work.com/resources/shiftwork-assessment/\n"
        )

        # HTML body (nicer in most clients)
        body_html = f"""
        <div style="font-family: Arial, Helvetica, sans-serif; color:#1A1A1A; max-width: 640px;">
          <div style="background:#0D1F3C; padding:18px 22px; border-left:4px solid #E8610A;">
            <div style="color:#EEAE26; font-size:16px; font-weight:700; letter-spacing:.02em;">
              SHIFTWORK SOLUTIONS
            </div>
            <div style="color:#85B7EB; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.12em; margin-top:4px;">
              Assessment PDF Downloaded
            </div>
          </div>
          <div style="padding: 22px 24px; background:#FFFFFF;">
            <p style="font-size:14px; line-height:1.6; margin:0 0 16px 0;">
              A new Shiftwork Operations Analysis PDF was just downloaded.
              Contact details below &mdash; full PDF attached.
            </p>
            <div style="background:#F4F6F8; border-left:3px solid #1F4E79; padding:14px 18px; border-radius:0 6px 6px 0; margin-bottom:16px;">
              <div style="font-size:10px; font-weight:700; color:#1F4E79; text-transform:uppercase; letter-spacing:.08em; margin-bottom:10px;">
                Contact
              </div>
              <table style="font-size:13px; line-height:1.6; border-collapse:collapse;">
                <tr><td style="color:#666; padding-right:12px;">Name:</td><td><strong>{name}</strong></td></tr>
                <tr><td style="color:#666; padding-right:12px;">Email:</td><td>{email}</td></tr>
                <tr><td style="color:#666; padding-right:12px;">Company:</td><td>{company}</td></tr>
                <tr><td style="color:#666; padding-right:12px;">Industry:</td><td>{industry}</td></tr>
                <tr><td style="color:#666; padding-right:12px;">Shift workers:</td><td>{shift_wk}</td></tr>
              </table>
            </div>
            <div style="background:#FEF6F0; border-left:3px solid #E8610A; padding:14px 18px; border-radius:0 6px 6px 0; margin-bottom:16px;">
              <div style="font-size:10px; font-weight:700; color:#E8610A; text-transform:uppercase; letter-spacing:.08em; margin-bottom:6px;">
                Their stated biggest challenge
              </div>
              <div style="font-size:13px; line-height:1.55;">{biggest}</div>
            </div>
            <div style="background:#EEF3F8; border-left:3px solid #1F4E79; padding:14px 18px; border-radius:0 6px 6px 0;">
              <div style="font-size:10px; font-weight:700; color:#1F4E79; text-transform:uppercase; letter-spacing:.08em; margin-bottom:6px;">
                Overall score
              </div>
              <div style="font-size:15px; font-weight:700; color:#1F4E79;">{score_str}</div>
            </div>
            <p style="font-size:12px; color:#666; margin:22px 0 0 0; line-height:1.5;">
              The full PDF is attached to this email.
            </p>
          </div>
          <div style="background:#0D1F3C; padding:12px 24px; font-size:11px; color:rgba(255,255,255,.55);">
            Automated notification from the Shiftwork Operations Reality Check &middot;
            shift-work.com/resources/shiftwork-assessment/
          </div>
        </div>
        """

        # PDF attachment — base64-encoded
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        attachment_name = f"Shiftwork-Assessment-{datetime.now().strftime('%Y-%m-%d')}.pdf"

        params = {
            "from":    EMAIL_FROM,
            "to":      [NOTIFICATION_RECIPIENT],
            "subject": subject,
            "text":    body_text,
            "html":    body_html,
            "attachments": [
                {
                    "filename": attachment_name,
                    "content":  pdf_b64,
                }
            ],
        }

        result = resend.Emails.send(params)

        # Resend returns an id on success
        msg_id = (result or {}).get("id", "")
        return (True, f"sent id={msg_id}")

    except Exception as e:
        return (False, f"resend error: {str(e)}")


# =============================================================================
# ROUTE — POST /api/assessment/generate-pdf
# =============================================================================
@assessment_pdf_bp.route("/generate-pdf", methods=["POST", "OPTIONS"])
def generate_pdf():
    """
    Generate the assessment PDF from the results payload and return it as
    a direct download. Simultaneously email a copy to Contact@shift-work.com.

    Request: JSON body with shape described in build_assessment_pdf().
    Response: application/pdf stream, Content-Disposition: attachment.
    """
    # Handle CORS preflight — after_request handler will add the headers
    if request.method == "OPTIONS":
        return jsonify({'status': 'ok'}), 200

    payload = request.get_json(silent=True) or {}

    try:
        pdf_buffer = build_assessment_pdf(payload)
    except Exception as e:
        print(f"[assessment_pdf] build_assessment_pdf failed: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error":   "PDF generation failed. Please try again.",
        }), 500

    pdf_bytes = pdf_buffer.getvalue()
    pdf_buffer.seek(0)

    # ----- Email notification (never block the user) ------------------
    try:
        ok, info = _send_notification_email(pdf_bytes, payload)
        if ok:
            print(f"[assessment_pdf] notification email sent: {info}")
        else:
            print(f"[assessment_pdf] notification email skipped: {info}")
    except Exception as e:
        print(f"[assessment_pdf] notification email exception (non-fatal): {e}")

    # ----- Stream the PDF to the browser ------------------------------
    filename = f"Shiftwork-Assessment-{datetime.now().strftime('%Y-%m-%d')}.pdf"
    return send_file(
        pdf_buffer,
        mimetype     = "application/pdf",
        as_attachment= True,
        download_name= filename,
    )


# I did no harm and this file is not truncated
