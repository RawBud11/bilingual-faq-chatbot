"""Settings in one place: model, files, categories, escalation, search, server limits.

Puentara is a fictional company used for this demo.
"""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

# --- Claude API -------------------------------------------------------------
# Used when ANTHROPIC_MODEL is not set in .env. A small, fast model is enough
# to turn one help article into a short chat answer.
DEFAULT_MODEL = "claude-haiku-5-5"
AI_TIMEOUT_SECONDS = 30
AI_MAX_TOKENS = 500
# Answers below this confidence are not shown: the customer gets the
# "I don't have an answer" message and a handoff offer instead.
CONFIDENCE_THRESHOLD = 0.7

PROMPT_FILE = PROJECT_DIR / "prompts" / "chat_system.txt"
FIXTURES_FILE = PROJECT_DIR / "fixtures" / "chat_answers.json"
KB_DIR = PROJECT_DIR / "kb"
DATA_DIR = PROJECT_DIR / "data"
STATIC_DIR = PROJECT_DIR / "static"
HANDOFFS_FILE = PROJECT_DIR / "output" / "handoffs.jsonl"

# --- Languages --------------------------------------------------------------
# A message that mixes English and Spanish gets a Spanish reply.
MIXED_REPLY_LANGUAGE = "es"
# A message with no English or Spanish words and fewer words than this ("ok",
# "1099?") is too short to call "another language": it gets the widget's
# UI language. Longer ones get the bilingual "English or Spanish only" message.
OTHER_LANGUAGE_MIN_WORDS = 3

# --- Categories and escalation (copied from bilingual-reply-assistant) ------
CATEGORIES = [
    "account_access",
    "identity_verification",
    "card_lost_stolen",
    "transfer_failed_pending",
    "charge_dispute",
    "fees",
    "tax_forms",
    "app_bug",
    "general_question",
]

# Default urgency of a handoff, per category (first column of #2's ROUTING).
CATEGORY_URGENCY = {
    "card_lost_stolen": "urgent",
    "charge_dispute": "high",
    "account_access": "high",
    "identity_verification": "high",
    "transfer_failed_pending": "high",
    "fees": "normal",
    "tax_forms": "normal",
    "app_bug": "normal",
    "general_question": "low",
}

# The bot may answer these from the article, but it always offers a person
# too: money, disputes and account access are decided by people.
OFFER_HANDOFF_CATEGORIES = {"charge_dispute", "account_access", "identity_verification"}

# --- Keyword search (BM25, copied from bilingual-reply-assistant) -----------
SEARCH_TOP_K = 2
# BM25 scores are not percentages. With 8 articles, one word that appears in
# only one article scores about 1.8, so 1.5 means "at least one fairly
# specific word in common". Below it: "I don't have an answer for that".
SEARCH_MIN_SCORE = 1.5
BM25_K1 = 1.5
BM25_B = 0.75

# --- Web server -------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8000
MAX_MESSAGE_CHARS = 1000
# The widget sends the conversation so far with every message (the server
# keeps no state). 20 turns of up to 2,000 characters fit well under 64 KB.
MAX_HISTORY_TURNS = 20
MAX_HISTORY_TEXT_CHARS = 2000
MAX_BODY_BYTES = 64 * 1024
# Other websites allowed to call /api/chat from a browser, for example
# ["https://help.example.com"]. Empty: only pages served by app.py itself.
CORS_ALLOWED_ORIGINS = []
