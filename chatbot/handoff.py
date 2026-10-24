"""Hand a conversation to a person: detect the request, build the record, save it.

A handoff record is one JSON line in output/handoffs.jsonl:
  id, time, language, reply_lang, category, urgency, trigger,
  summary (one line in English and one in Spanish), transcript (masked)
The summary is built from fixed templates, not by the AI, so it is the same
every time and never invents facts. Nothing is sent anywhere: this demo does
not connect to a real helpdesk.
"""

import json
import re
import threading
from datetime import datetime, timezone

import config

from .mask import mask_sensitive
from .rules import fold
from .strings import STRINGS

URGENCY_ORDER = ["low", "normal", "high", "urgent"]

# "Talk to a person", "quiero hablar con alguien", "get me an agent".
PEOPLE_EN = r"(a |an |some |one |your )?(real |live |actual )?(person|human|agent|someone|somebody|representative|rep|operator)"
PEOPLE_ES = r"(alguien|una persona|un agente|un asesor|una asesora|un humano|un operador|una operadora|soporte)"
HUMAN_REQUEST_RE = re.compile("|".join([
    rf"\b(talk|speak|chat) (to|with) {PEOPLE_EN}\b",
    rf"\b(get|give|connect|transfer|put|pass) me (to |through to |with )?{PEOPLE_EN}\b",
    r"\b(real|live|actual) (human|person|agent)\b",
    r"\bhablar con " + PEOPLE_ES,
    r"\b(me )?(pasas|pasa|pasame|comunicas|comunica|comunicame|transfieres|transfiere) con " + PEOPLE_ES,
    r"\b(persona|agente|asesor|asesora|humano) (real|de verdad)\b",
    r"\bque me atienda " + PEOPLE_ES,
    # Short requests: "I want a human", "need an agent",
    # "quiero un humano", "necesito un agente". The people word must follow the
    # verb closely, so "quiero pagarle a alguien" is not a request.
    r"\b(i want|i need|i'd like|i would like|i wanna|can i (get|have)|let me (talk|speak) to)"
    r" (to (talk|speak|chat) (to|with) )?(a |an |some |one )?(real |live |actual )?"
    r"(human|person|agent|representative|rep|operator|someone|somebody)\b(?!'s)",
    r"\b(quiero|necesito|quisiera|me gustaria|puedo tener)"
    r" (que me atienda |hablar con |un |una |a )?(un |una )?"
    r"(humano|humana|persona|agente|asesor|asesora|representante|operador|operadora|alguien)\b"
    r"(?! (a quien|que reciba|para (enviar|pagar|mandar)))",
    # A message that is only a people word, maybe with "please" or "por favor":
    # "agent", "human please", "representative please", "un asesor, por favor".
    r"^\W*(please |por favor |hola |hi )?(a |an |un |una )?(real |live )?"
    r"(human|person|agent|representative|rep|operator|humano|persona|agente|asesor|asesora"
    r"|representante|operador|operadora)\W*(please|pls|plz|por favor|ya|now|ahora)?\W*$",
]))


def wants_human(text):
    """True when the customer asks for a person, in English or Spanish."""
    return bool(HUMAN_REQUEST_RE.search(fold(text)))


def higher_urgency(a, b):
    return a if URGENCY_ORDER.index(a) >= URGENCY_ORDER.index(b) else b


def clean_history(history):
    """Turn the widget's history into a safe, masked transcript.

    The history comes from the browser, so it is not trusted: unknown roles
    are dropped, text is cut to a maximum length and masked again here.
    """
    transcript = []
    for item in (history or [])[-config.MAX_HISTORY_TURNS:]:
        if not isinstance(item, dict) or item.get("role") not in ("customer", "bot"):
            continue
        text = str(item.get("text") or "")[:config.MAX_HISTORY_TEXT_CHARS]
        entry = {"role": item["role"], "text": mask_sensitive(text)[0]}
        if item["role"] == "bot" and isinstance(item.get("action"), str):
            entry["action"] = item["action"][:40]
        transcript.append(entry)
    return transcript


def summary_line(lang, urgency, category, language, trigger, last_message):
    s = STRINGS[lang]
    last = " ".join(last_message.split())
    if len(last) > 160:
        last = last[:157] + "..."
    return s["summary"].format(urgency=s["urgency"][urgency], category=s["categories"][category],
                               language=s["languages"][language], trigger=s["triggers"][trigger],
                               last=last)


def build_record(*, language, reply_lang, category, urgency, trigger, transcript):
    """Everything an agent needs, except the id (the store adds it)."""
    customer_lines = [e["text"] for e in transcript if e["role"] == "customer"]
    last = customer_lines[-1] if customer_lines else ""
    return {
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "language": language,
        "reply_lang": reply_lang,
        "category": category,
        "urgency": urgency,
        "trigger": trigger,
        "summary": {lang: summary_line(lang, urgency, category, language, trigger, last)
                    for lang in ("en", "es")},
        "transcript": transcript,
    }


class JsonlStore:
    """Appends handoff records to a JSONL file and numbers them H-0001, H-0002...

    The lock matters because the web server answers requests in threads: two
    customers asking for a person at the same moment must not get the same id.
    """

    def __init__(self, path=config.HANDOFFS_FILE):
        self.path = path
        self.lock = threading.Lock()

    def add(self, make_record):
        """make_record(ref) -> record. It gets the new id first, because the
        customer's reply (saved in the transcript) quotes the reference."""
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            ref = f"H-{len(self.read_all()) + 1:04d}"
            record = {"id": ref, **make_record(ref)}
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return ref

    def read_all(self):
        if not self.path.exists():
            return []
        records = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # a half-written or hand-edited line: skip it
        return records

    def reset(self):
        """Start an empty file (demo.py does this so ids start at H-0001)."""
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")


class MemoryStore:
    """Same interface as JsonlStore, keeps records in a list (evaluate.py, tests)."""

    def __init__(self):
        self.records = []

    def add(self, make_record):
        ref = f"H-{len(self.records) + 1:04d}"
        self.records.append({"id": ref, **make_record(ref)})
        return ref

    def read_all(self):
        return list(self.records)
