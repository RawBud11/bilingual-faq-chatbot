"""The chat server: widget, chat API, agent inbox. Python standard library only.

Usage:
  python app.py                 demo mode (no API key needed)
  python app.py --port 8001     if port 8000 is busy
  python app.py --live          real Claude answers (needs ANTHROPIC_API_KEY in .env)

Routes:
  POST /api/chat      {"message": "...", "history": [...], "ui_lang": "en"} -> bot reply
  POST /api/handoff   {"history": [...], "ui_lang": "es"}                  -> handoff reference
  GET  /api/status    demo mode or live, and the message length limit (for the widget)
  GET  /agent         read-only agent inbox (?lang=es for Spanish)
  GET  /kb/<id>       one help article, for the "Source" links
  GET  /<file>        files from static/ (the demo help page and the widget)

A local demo, not production-hardened: no login, no rate limiting.
Puentara is a fictional company.
"""

import argparse
import json
import sys
import traceback
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

import config
from chatbot.handoff import JsonlStore
from chatbot.kb import load_kb
from chatbot.modes import UserError, make_client
from chatbot.pages import render_article, render_inbox
from chatbot.retrieve import build_indexes
from chatbot.strings import STRINGS, t
from chatbot.turn import run_button_handoff, run_turn

STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml",
                ".ico": "image/x-icon"}


class BadRequest(Exception):
    """Sent back as JSON with an English and a Spanish message."""

    def __init__(self, status, key):
        super().__init__(key)
        self.status, self.key = status, key


def error_body(key):
    return {"error": key, "message": {"en": STRINGS["en"][key], "es": STRINGS["es"][key]}}


def public_view(result, demo):
    """The part of a turn the browser gets. Internal details (a blocked
    answer, the checker's finding, AI error codes) never leave the server."""
    source = result["source"]
    return {
        "reply": result["reply"], "reply_lang": result["reply_lang"], "action": result["action"],
        "source": {**source, "url": f"/kb/{source['id']}"} if source else None,
        "offer_handoff": result["offer_handoff"],
        "handoff": result["handoff"]["id"] if result["handoff"] else None,
        "demo": demo,
    }


def safe_static_path(url_path):
    """Map a URL path to a file inside static/, or None.

    The path is decoded and resolved first, then it must still be inside
    static/: "/../config.py", "/%2e%2e/.env" and "/..%5cconfig.py" all fail.
    """
    relative = unquote(url_path).lstrip("/") or "index.html"
    if "\x00" in relative:
        return None
    root = config.STATIC_DIR.resolve()
    try:
        candidate = (root / relative).resolve()
    except (OSError, ValueError):
        return None
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate if candidate.suffix.lower() in STATIC_TYPES else None


class ChatHandler(BaseHTTPRequestHandler):
    server_version = "PuentaraDemo/1.0"

    # --- small helpers ----------------------------------------------------
    def send(self, status, body, content_type, extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if content_type.startswith("text/html"):
            self.send_header("Content-Security-Policy", "default-src 'self'")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, status, obj):
        self.send(status, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8",
                  self.cors_headers())

    def cors_headers(self):
        origin = self.headers.get("Origin")
        if origin and origin in config.CORS_ALLOWED_ORIGINS:
            return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
        return {}

    def origin_allowed(self):
        """Browsers send Origin on cross-site POSTs. Allow our own pages and
        the CORS allowlist; tools like curl send no Origin and are allowed."""
        origin = self.headers.get("Origin")
        own = f"http://{self.headers.get('Host', '')}"
        return origin is None or origin == own or origin in config.CORS_ALLOWED_ORIGINS

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise BadRequest(411, "error_bad_request") from None
        if length < 0:
            raise BadRequest(400, "error_bad_request")
        if length > config.MAX_BODY_BYTES:
            # Read and drop the body (up to 1 MB) before answering. If the server
            # answers while the client is still sending, Windows may reset the
            # connection and the client never sees the 413 message.
            self.rfile.read(min(length, 1024 * 1024))
            self.close_connection = True
            raise BadRequest(413, "error_too_big")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BadRequest(400, "error_bad_request") from None
        if not isinstance(data, dict):
            raise BadRequest(400, "error_bad_request")
        history = data.get("history", [])
        data["history"] = history if isinstance(history, list) else []
        data["ui_lang"] = data.get("ui_lang") if data.get("ui_lang") in ("en", "es") else "en"
        return data

    def log_message(self, format, *args):
        if not self.server.bot.get("quiet"):
            super().log_message(format, *args)

    # --- routes -------------------------------------------------------------
    def do_GET(self):
        url = urlsplit(self.path)
        bot = self.server.bot
        if url.path == "/agent":
            lang = parse_qs(url.query).get("lang", ["en"])[0]
            lang = lang if lang in ("en", "es") else "en"
            store = bot["store"]
            html = render_inbox(store.read_all(), lang, store.path.name)
            return self.send(200, html, STATIC_TYPES[".html"])
        if url.path == "/api/status":
            return self.send_json(200, {"demo": bot["demo"], "max_chars": config.MAX_MESSAGE_CHARS})
        if url.path.startswith("/kb/"):
            article = bot["articles"].get(url.path[4:])
            lang = article.lang if article else "en"
            return self.send(200 if article else 404, render_article(article, lang), STATIC_TYPES[".html"])
        path = safe_static_path(url.path)
        if path is None:
            return self.send(404, "Not found", "text/plain; charset=utf-8")
        self.send(200, path.read_bytes(), STATIC_TYPES[path.suffix.lower()])

    do_HEAD = do_GET

    def do_POST(self):
        route = {"/api/chat": self.chat, "/api/handoff": self.handoff}.get(urlsplit(self.path).path)
        if route is None:
            return self.send_json(404, {"error": "not_found"})
        if not self.origin_allowed():
            return self.send_json(403, {"error": "origin_not_allowed"})
        try:
            self.send_json(200, route(self.read_json()))
        except BadRequest as error:
            self.send_json(error.status, error_body(error.key))
        except Exception:  # a bug: log it here, show the customer a short message
            traceback.print_exc()
            self.send_json(500, error_body("error_server"))

    def do_OPTIONS(self):
        """CORS preflight, only for origins in config.CORS_ALLOWED_ORIGINS."""
        headers = self.cors_headers()
        if not headers:
            return self.send(403, "", "text/plain; charset=utf-8")
        headers.update({"Access-Control-Allow-Methods": "POST, GET",
                        "Access-Control-Allow-Headers": "Content-Type"})
        self.send(204, "", "text/plain; charset=utf-8", headers)

    def chat(self, data):
        message = data.get("message")
        if not isinstance(message, str) or not message.strip():
            raise BadRequest(400, "error_empty")
        if len(message) > config.MAX_MESSAGE_CHARS:
            raise BadRequest(400, "error_too_long")
        bot = self.server.bot
        result = run_turn(message, data["history"], client=bot["client"], indexes=bot["indexes"],
                          store=bot["store"], ui_lang=data["ui_lang"], model=bot["model"])
        if result.get("ai_fatal"):  # bad key or model: tell the person running the server
            problem = t(bot["ui_lang"], "ai_problems")[result["ai_problem"]]
            print(t(bot["ui_lang"], "fatal_ai").format(error=problem), file=sys.stderr)
        return public_view(result, bot["demo"])

    def handoff(self, data):
        bot = self.server.bot
        result = run_button_handoff(data["history"], store=bot["store"],
                                    ui_lang=data["ui_lang"])
        return public_view(result, bot["demo"])


class ChatServer(ThreadingHTTPServer):
    # On Windows, address reuse lets a second server bind a port that is
    # already in use, so "port busy" would never be reported. Turn it off there.
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


def make_server(host, port, *, client, model, demo, store=None, ui_lang="en", quiet=False):
    """Build (but do not start) the server. Port 0 picks a free port (tests)."""
    kb = load_kb()
    server = ChatServer((host, port), ChatHandler)
    server.bot = {"client": client, "model": model, "demo": demo, "ui_lang": ui_lang,
                  "indexes": build_indexes(kb), "store": store or JsonlStore(),
                  "articles": {a.id: a for articles in kb.values() for a in articles},
                  "quiet": quiet}
    return server


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Puentara (fictional company) FAQ chatbot server")
    parser.add_argument("--host", default=config.HOST)
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--live", action="store_true", help="call Claude (needs ANTHROPIC_API_KEY in .env)")
    parser.add_argument("--ui-lang", choices=["en", "es"], default="en", help="language of these terminal messages")
    parser.add_argument("--handoffs", type=Path, default=config.HANDOFFS_FILE, help="handoff file (JSONL)")
    args = parser.parse_args(argv)
    try:
        client, model, mode_line, demo = make_client(args.live, args.ui_lang)
        server = make_server(args.host, args.port, client=client, model=model, demo=demo,
                             store=JsonlStore(args.handoffs), ui_lang=args.ui_lang)
    except UserError as error:
        sys.exit(str(error))
    except OSError:
        sys.exit(t(args.ui_lang, "port_busy").format(port=args.port, next_port=args.port + 1))
    print(mode_line, flush=True)
    print(t(args.ui_lang, "server_open").format(host=args.host, port=server.server_address[1]), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print(t(args.ui_lang, "stopped"))


if __name__ == "__main__":
    main()
