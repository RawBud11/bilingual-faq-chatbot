"""Pick live mode or demo mode, shared by app.py and demo.py.

Demo mode is the default: no key needed, sample answers from fixtures/.
Live mode only with --live AND a key in .env, so nobody spends money by accident.
"""

import os

from dotenv import load_dotenv

import config

from .ai import FixtureClient, LiveClient, RecordingClient
from .strings import t


class UserError(Exception):
    """A problem the user can fix; printed as one line, no stack trace."""


def make_client(live, lang, record=False):
    """Returns (client, model, mode_line, is_demo)."""
    load_dotenv(config.PROJECT_DIR / ".env")
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key == "your-key-here":  # the placeholder from .env.example
        api_key = ""
    model = os.getenv("ANTHROPIC_MODEL", "").strip() or config.DEFAULT_MODEL
    if record and not live:
        raise UserError(t(lang, "record_needs_live"))
    if live:
        if not api_key:
            raise UserError(t(lang, "need_key"))
        client = LiveClient(api_key, model)
        if record:
            client = RecordingClient(client)
        return client, model, t(lang, "live_mode").format(model=model), False
    line = t(lang, "demo_with_key") if api_key else t(lang, "demo_no_key")
    return FixtureClient(), model, line, True
