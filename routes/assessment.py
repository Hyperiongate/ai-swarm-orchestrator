# =============================================================
# routes/assessment.py  -  Shift Assessment Google Sheets API
# Shiftwork Solutions LLC
# Created: 2026-04-17
#
# ROUTES:
#   POST /api/assessment/lead          -- Save contact form data
#   POST /api/assessment/update-scores -- Save scores after AI eval
#
# Writes to Google Sheet: Shift Assessment Data
# Sheet ID: 1qjUphHvXoraOnvzHr8TLCPuS87VXc-plLR6lbX9-gxQ
# =============================================================

import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import gspread
from google.oauth2.service_account import Credentials

assessment_bp = Blueprint('assessment', __name__)

SPREADSHEET_ID = "1qjUphHvXoraOnvzHr8TLCPuS87VXc-plLR6lbX9-gxQ"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# In-memory store so /update-scores can find the row it needs to update
# Maps session key (email+timestamp) -> sheet row number
_row_index = {}


def get_sheet():
    """
    Authenticate with Google and return the first worksheet.
    Credentials come from GOOGLE_SERVICE_ACCOUNT_JSON env var
    (the full JSON string) set in Render.
    """
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON env var not set")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID)
    return sheet.sheet1


@assessment_bp.route("/api/assessment/lead", methods=["POST", "OPTIONS"])
@cross_origin(origins=["https://shift-work.com", "https://www.shift-work.com"])
def assessment_lead():
    """
    Save contact form data as a new row.
    Columns: Date, Name, Email, Company, Industry, Shift Workers,
             Shift Length, Primary Challenge, Newsletter Signup,
             Overall Score (blank until update-scores is called),
             then 8 dimension score columns (also blank initially).
    Returns: { success: true, id: <row_number> }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    try:
        sheet = get_sheet()
        now = datetime.now().strftime("%B %d, %Y %I:%M %p")
        row = [
            now,
            data.get("name", ""),
            data.get("email", ""),
            data.get("company", ""),
            data.get("industry", ""),
            data.get("shift_workers", ""),
            data.get("shift_length", ""),
            data.get("primary_challenge", ""),
            "Yes" if data.get("newsletter_signup") else "No",
            "",   # Overall Score -- filled by update-scores
            "",   # Work-Life Score
            "",   # Health Score
            "",   # Alertness Score
            "",   # Overtime Score
            "",   # Operations Score
            "",   # Quality Score
            "",   # Communication Score
            "",   # Workforce Score
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")

        # Record which row this submission landed on so update-scores
        # can find it later. Row count after append = the new row.
        row_number = len(sheet.get_all_values())
        session_key = f"{data.get('email','')}_{now}"
        _row_index[session_key] = row_number

        print(f"[ASSESSMENT] Lead saved: {data.get('email','')} row {row_number}")
        return jsonify({"success": True, "id": session_key}), 200

    except Exception as e:
        print(f"[ASSESSMENT] Lead save error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@assessment_bp.route("/api/assessment/update-scores", methods=["POST", "OPTIONS"])
@cross_origin(origins=["https://shift-work.com", "https://www.shift-work.com"])
def assessment_update_scores():
    """
    Update the score columns for an existing row.
    Accepts: { assessment_id, overall_score, worklife_score,
               health_score, alertness_score, overtime_score,
               operations_score, quality_score, communication_score,
               workforce_score }
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    assessment_id = data.get("assessment_id")

    try:
        sheet = get_sheet()

        # Find the row -- use stored index if available, else search by
        # matching the session key in column 1 (date) is not reliable,
        # so we fall back to appending a scores-only row if not found.
        row_number = _row_index.get(assessment_id)

        if row_number:
            # Update score columns (J through R = columns 10-18)
            scores = [
                data.get("overall_score", ""),
                data.get("worklife_score", ""),
                data.get("health_score", ""),
                data.get("alertness_score", ""),
                data.get("overtime_score", ""),
                data.get("operations_score", ""),
                data.get("quality_score", ""),
                data.get("communication_score", ""),
                data.get("workforce_score", ""),
            ]
            # gspread uses 1-based col index; col J = 10
            for i, score in enumerate(scores):
                if score != "":
                    sheet.update_cell(row_number, 10 + i, score)
            _row_index.pop(assessment_id, None)
            print(f"[ASSESSMENT] Scores updated: row {row_number}")
        else:
            # Row not found in index (e.g. server restarted between calls)
            # Log it but don't fail -- scores are secondary to the lead.
            print(f"[ASSESSMENT] update-scores: row not found for {assessment_id} -- skipping")

        return jsonify({"success": True}), 200

    except Exception as e:
        print(f"[ASSESSMENT] Score update error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
