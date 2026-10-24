"""End-to-end runs of demo.py, evaluate.py, app.py and the data script, in demo
mode, plus checks that both languages have the same texts. No network, no key."""

import csv
import json
import socket
import sys

import pytest

import app
import config
import demo
import evaluate
from chatbot import modes
from chatbot.strings import STRINGS

sys.path.insert(0, str(config.PROJECT_DIR / "scripts"))
import make_conversations  # noqa: E402


@pytest.fixture(autouse=True)
def no_key(monkeypatch):
    # Ignore any real .env on this machine: tests must never call the API.
    monkeypatch.setattr(modes, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)


def test_demo_plays_six_conversations_and_writes_three_handoffs(tmp_path, capsys):
    out = tmp_path / "handoffs.jsonl"
    demo.main(["--handoffs", str(out)])
    printed = capsys.readouterr().out
    assert printed.startswith("Demo mode: no API key found, using sample answers from fixtures/")
    assert printed.count("=== ") == 6
    assert "[CARD NUMBER MASKED]" in printed
    assert "Handoff H-0001 (urgent, card_lost_stolen)" in printed
    assert "source: KB-ES-04" in printed
    assert "the checker blocked an answer (asks_sensitive); the customer never saw it" in printed
    assert "send me your CVV" not in printed
    assert "3 handoffs written to" in printed and "Nothing was sent." in printed
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in records] == ["H-0001", "H-0002", "H-0003"]
    assert "0000 " not in out.read_text(encoding="utf-8")  # the fake card number is masked


def test_demo_starts_a_fresh_file_each_run(tmp_path, capsys):
    out = tmp_path / "handoffs.jsonl"
    demo.main(["--handoffs", str(out)])
    demo.main(["--handoffs", str(out)])
    assert len(out.read_text(encoding="utf-8").splitlines()) == 3


def test_demo_in_spanish(tmp_path, capsys):
    demo.main(["--handoffs", str(tmp_path / "h.jsonl"), "--ui-lang", "es"])
    printed = capsys.readouterr().out
    assert printed.startswith("Modo demo: no se encontró una clave de API")
    assert "Traspaso H-0001 (urgent, card_lost_stolen)" in printed
    assert "Se escribieron 3 traspasos" in printed and "No se envió nada." in printed


@pytest.mark.parametrize("argv,expected", [
    (["--live"], "--live needs an API key"),
    (["--record"], "--record only works with --live"),
    (["--live", "--ui-lang", "es"], "--live necesita una clave de API"),
])
def test_clear_messages_for_user_errors(tmp_path, argv, expected):
    with pytest.raises(SystemExit) as info:
        demo.main(argv + ["--handoffs", str(tmp_path / "h.jsonl")])
    assert expected in str(info.value.code)


def test_placeholder_key_from_env_example_counts_as_no_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "your-key-here")
    _, model, line, is_demo = modes.make_client(False, "en")
    assert is_demo and line.startswith("Demo mode: no API key found")
    assert model == config.DEFAULT_MODEL == "claude-haiku-5-5"


def test_model_comes_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test-model")
    assert modes.make_client(False, "en")[1] == "claude-test-model"


def test_app_says_when_the_port_is_busy(capsys):
    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    busy.listen()
    port = busy.getsockname()[1]
    try:
        with pytest.raises(SystemExit) as info:
            app.main(["--port", str(port)])
        assert f"Port {port} is busy" in str(info.value.code)
        assert f"--port {port + 1}" in str(info.value.code)
    finally:
        busy.close()


def test_app_live_without_key_gives_a_clear_message():
    with pytest.raises(SystemExit) as info:
        app.main(["--live", "--port", "0"])
    assert "--live needs an API key" in str(info.value.code)


@pytest.mark.parametrize("lang,header", [
    ("en", "Synthetic sample data. Not real-world accuracy."),
    ("es", "Datos de ejemplo sintéticos. No miden la precisión en el mundo real."),
])
def test_evaluate_runs_offline_and_labels_data_synthetic(lang, header, capsys):
    evaluate.main(["--ui-lang", lang])
    printed = capsys.readouterr().out
    assert printed.startswith(header)
    assert "first run" in printed or "primera ejecución" in printed
    assert "chat_fresh.csv" in printed


def test_evaluate_reports_the_fresh_set_on_its_own_line(tmp_path, monkeypatch, capsys):
    fresh = tmp_path / "fresh.csv"
    fresh.write_text("id,lang,kind,message,expected\nF1,en,paraphrase,I want to talk to a person,handoff_requested\n",
                     encoding="utf-8")
    monkeypatch.setattr(evaluate, "FRESH_FILE", fresh)
    evaluate.main([])
    assert "never tuned on): 1/1 (100%)" in capsys.readouterr().out


def test_first_run_is_saved():
    saved = (config.PROJECT_DIR / "docs" / "eval_first_run.txt").read_text(encoding="utf-8")
    assert saved.startswith("Synthetic sample data. Not real-world accuracy.")
    assert "Overall correct action: 70/76 (92%)" in saved


def test_labeled_set_has_the_planned_shape():
    with open(evaluate.LABELED_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 70
    assert len({r["id"] for r in rows}) == len(rows)
    assert sum(r["kind"] == "paraphrase" for r in rows) >= len(rows) / 2
    assert {r["lang"] for r in rows} >= {"en", "es", "mixed"}
    allowed = {"handoff_urgent", "handoff_requested", "refuse_account", "no_answer", "sensitive_warning"}
    for row in rows:
        assert row["expected"] in allowed or row["expected"].startswith("answer:0"), row["id"]
    with open(evaluate.FRESH_FILE, newline="", encoding="utf-8") as f:
        assert next(csv.reader(f)) == ["id", "lang", "kind", "message", "expected"]


def test_conversations_file_is_reproducible_from_the_seed(tmp_path, capsys):
    out = tmp_path / "conv.json"
    make_conversations.main(["--seed", "42", "--out", str(out)])
    committed = (config.DATA_DIR / "demo_conversations.json").read_text(encoding="utf-8")
    assert out.read_text(encoding="utf-8") == committed
    assert "0000 " in committed  # fake card numbers start with 0000


def compare_keys(a, b, path=""):
    assert set(a) == set(b), path
    for key, value in a.items():
        if isinstance(value, dict):
            compare_keys(value, b[key], f"{path}.{key}")


def test_both_languages_have_the_same_strings():
    compare_keys(STRINGS["en"], STRINGS["es"])


def test_widget_has_the_same_labels_in_both_languages():
    js = (config.STATIC_DIR / "widget.js").read_text(encoding="utf-8")
    en = js[js.index("en: {"):js.index("es: {")]
    es = js[js.index("es: {"):js.index("var MAX_CHARS")]
    keys = lambda block: sorted(line.split(":")[0].strip() for line in block.splitlines()[1:]  # noqa: E731
                                if ":" in line and not line.strip().startswith(("//", '"')))
    assert keys(en) == keys(es)
    assert "Hablar con una persona" in es and "Talk to a person" in en
