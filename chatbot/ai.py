"""The AI step: build the request, call Claude (or read a fixture), check the answer.

Adapted from bilingual-reply-assistant (reply_assistant/ai.py), not imported
across repos. Three clients share one method, complete(request) -> raw text:
  LiveClient       real call through the official anthropic SDK (--live)
  FixtureClient    demo mode: saved answers from fixtures/chat_answers.json
  RecordingClient  wraps LiveClient and saves its answers (demo.py --live --record)
Any problem raises AIError. The caller turns it into "I don't have an answer".
"""

import json
import re
from datetime import date

import config

from .language import strip_accents

LANGUAGE_NAMES = {"en": "English", "es": "Spanish"}
CITATION_RE = re.compile(r"\[(KB-[A-Z]{2}-\d{2})\]")
TAG_RE = re.compile(r"<\s*/?\s*(ticket|articles?)\b[^>]*>", re.IGNORECASE)


class AIError(Exception):
    """An AI problem. `code` is a key in strings.py "ai_problems".

    fatal=True means every message would fail the same way (bad key, unknown
    model), so the server logs a clear message; the customer still gets the
    safe "no answer" reply.
    """

    def __init__(self, code, fatal=False):
        super().__init__(code)
        self.code = code
        self.fatal = fatal


def strip_tags(text):
    """Remove <ticket> / <article> tags typed by a customer, so their message
    cannot "close" its block and pretend to be instructions or an article."""
    return TAG_RE.sub("[tag removed]", text)


def fixture_key(text):
    """Normalize a message so small differences still find its fixture:
    lowercase, no accents, no punctuation, single spaces."""
    words = re.findall(r"[a-z0-9\[\]]+", strip_accents(text))
    return " ".join(words)


def build_request(message, articles, reply_lang, model):
    """Build the API request. The message must already be masked."""
    system = config.PROMPT_FILE.read_text(encoding="utf-8")
    system = system.replace("{reply_language}", LANGUAGE_NAMES[reply_lang])
    blocks = [f'<article id="{a.id}">\n# {a.title}\n{a.body}\n</article>' for a in articles]
    user = ("<articles>\n" + "\n".join(blocks) + "\n</articles>\n\n"
            f"<ticket>\n{strip_tags(message)}\n</ticket>")
    return {
        "key": fixture_key(message),  # used by fixtures, not sent to the API
        "reply_lang": reply_lang,     # same
        "model": model,
        "max_tokens": config.AI_MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }


def parse_answer(text, retrieved_ids, threshold=config.CONFIDENCE_THRESHOLD):
    """Turn the model's text into {"reply", "cited", "confidence"} or raise AIError.

    The answer must cite at least one article, and only articles that the
    search actually returned. This checks the citation, not that the answer
    faithfully matches the article.
    """
    # Models sometimes wrap JSON in ```json fences or add a sentence; take the
    # first {...} block and ignore the rest.
    found = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not found:
        raise AIError("bad_json")
    try:
        data = json.loads(found.group(0))
    except json.JSONDecodeError:
        raise AIError("bad_json") from None
    if not isinstance(data, dict):
        raise AIError("bad_json")
    reply = str(data.get("reply") or "").strip()
    if not reply:
        raise AIError("no_reply")
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) \
            or not 0 <= confidence <= 1:
        raise AIError("bad_confidence")
    if confidence < threshold:
        raise AIError("low_confidence")
    cited = list(dict.fromkeys(CITATION_RE.findall(reply)))
    if not cited:
        raise AIError("no_citation")
    if any(article_id not in retrieved_ids for article_id in cited):
        raise AIError("bad_citation")
    return {"reply": reply, "cited": cited, "confidence": float(confidence)}


class LiveClient:
    def __init__(self, api_key, model, sdk_client=None):
        # Imported here, not at the top: the SDK takes a moment to load and
        # demo mode does not need it.
        import anthropic
        self.model = model
        # sdk_client lets tests pass a fake, so tests never touch the network.
        self.sdk = sdk_client or anthropic.Anthropic(
            api_key=api_key, timeout=config.AI_TIMEOUT_SECONDS, max_retries=2)

    def complete(self, request):
        import anthropic  # already loaded by __init__, so this is instant
        try:
            response = self.sdk.messages.create(
                model=request["model"], max_tokens=request["max_tokens"],
                system=request["system"], messages=request["messages"])
        except anthropic.AuthenticationError:
            raise AIError("auth", fatal=True) from None
        except anthropic.PermissionDeniedError:
            raise AIError("permission", fatal=True) from None
        except anthropic.NotFoundError:
            raise AIError("model", fatal=True) from None
        except anthropic.APITimeoutError:
            raise AIError("timeout") from None
        except anthropic.APIConnectionError:
            raise AIError("connection") from None
        except anthropic.RateLimitError:
            raise AIError("rate_limit") from None
        except anthropic.BadRequestError:
            raise AIError("bad_request") from None
        except anthropic.APIError:
            raise AIError("server") from None
        return "".join(block.text for block in response.content
                       if getattr(block, "type", "") == "text")

    def source_for(self, request):
        return "live"


class FixtureClient:
    """Demo mode. Fixture file layout:
    {"answers": {"<normalized message>": {"en": {"source": "hand-written", "response": {...}}}}}
    "response" is a JSON object, or a string for raw (possibly broken) text.
    A message with no fixture raises AIError("no_fixture"): the turn then
    builds a template answer (no AI) from the top article.
    """

    def __init__(self, path=config.FIXTURES_FILE):
        with open(path, encoding="utf-8") as f:
            self.answers = json.load(f).get("answers", {})

    def _entry(self, request):
        return self.answers.get(request["key"], {}).get(request["reply_lang"])

    def complete(self, request):
        entry = self._entry(request)
        if entry is None:
            raise AIError("no_fixture")
        response = entry["response"]
        return response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)

    def source_for(self, request):
        """ "hand-written" or "recorded", as labeled in the fixture file."""
        entry = self._entry(request)
        return entry["source"] if entry else "template"


class TemplateOnlyClient:
    """Never has an answer, so every turn uses the template (evaluate.py)."""

    def complete(self, request):
        raise AIError("no_fixture")

    def source_for(self, request):
        return "template"


class RecordingClient:
    """Calls the live client and keeps every raw answer, to save as fixtures."""

    def __init__(self, live_client):
        self.live = live_client
        self.model = live_client.model
        self.recorded = []  # (key, reply_lang, raw_text)

    def complete(self, request):
        text = self.live.complete(request)
        self.recorded.append((request["key"], request["reply_lang"], text))
        return text

    def source_for(self, request):
        return "live"

    def save(self, path=config.FIXTURES_FILE):
        """Merge recorded answers into the fixture file, labeled "recorded"."""
        data = {"answers": {}}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        today = date.today().isoformat()
        for key, lang, text in self.recorded:
            try:
                response = json.loads(text)  # store readable JSON when possible
            except json.JSONDecodeError:
                response = text
            data.setdefault("answers", {}).setdefault(key, {})[lang] = {
                "source": "recorded", "model": self.live.model,
                "recorded_at": today, "response": response}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return len(self.recorded)
