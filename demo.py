"""Play the 6 scripted demo conversations in the terminal.

Usage:
  python demo.py
  python demo.py --ui-lang es
  python demo.py --live            (needs ANTHROPIC_API_KEY in .env)
  python demo.py --live --record   (also saves the real answers to fixtures/)

Each run starts a fresh output/handoffs.jsonl, so the references start at
H-0001. Nothing is sent to anyone. Puentara is a fictional company.
"""

import argparse
import json
import sys
from pathlib import Path

import config
from chatbot.handoff import JsonlStore
from chatbot.kb import load_kb
from chatbot.modes import UserError, make_client
from chatbot.retrieve import build_indexes
from chatbot.strings import STRINGS, t
from chatbot.turn import run_button_handoff, run_turn

CONVERSATIONS_FILE = config.DATA_DIR / "demo_conversations.json"


def display_path(path):
    """output/handoffs.jsonl instead of a long absolute path, when possible."""
    try:
        return path.resolve().relative_to(config.PROJECT_DIR).as_posix()
    except ValueError:
        return str(path)


def answer_from_text(result, ui, model):
    return STRINGS[ui]["sources"].get(result["answer_from"], result["answer_from"]).format(model=model)


def print_turn(result, ui, model):
    d = STRINGS[ui]["demo"]
    if result["masked_count"]:
        print(d["masked"].format(count=result["masked_count"], text=result["masked_message"]))
    print(f'{d["bot"]}: {result["reply"]}')
    print(d["details"].format(action=result["action"], language=result["language"],
                              reply_lang=result["reply_lang"]))
    if result["source"]:
        print(d["source"].format(source=result["source"]["id"], title=result["source"]["title"],
                                 answer_from=answer_from_text(result, ui, model)))
    if result["blocked"]:
        print(d["blocked"].format(reason=result["blocked"]["kind"]))
    if result.get("ai_problem"):
        print("  -> " + STRINGS[ui]["ai_problems"].get(result["ai_problem"], result["ai_problem"]))
    if result["handoff"]:
        h = result["handoff"]
        print(d["handoff"].format(ref=h["id"], urgency=h["urgency"], category=h["category"]))


def play(conversations, client, model, ui, store, indexes):
    """Play every conversation. Returns the number of handoffs written."""
    d = STRINGS[ui]["demo"]
    handoffs = 0
    for number, conversation in enumerate(conversations, start=1):
        print(d["title"].format(n=number, title=conversation["title"][ui]))
        history = []
        for turn in conversation["turns"]:
            if turn.get("button"):
                print(f'{d["customer"]}: {d["button"]}')
                result = run_button_handoff(history, store=store, ui_lang=ui)
            else:
                print(f'{d["customer"]}: {turn["say"]}')
                result = run_turn(turn["say"], history, client=client, indexes=indexes,
                                  store=store, ui_lang=ui, model=model)
                # The widget keeps what the customer typed; the server masks it again.
                history.append({"role": "customer", "text": turn["say"]})
            print_turn(result, ui, model)
            if result.get("ai_fatal"):
                problem = STRINGS[ui]["ai_problems"][result["ai_problem"]]
                raise UserError(t(ui, "fatal_ai").format(error=problem))
            history.append({"role": "bot", "text": result["reply"], "action": result["action"]})
            handoffs += 1 if result["handoff"] else 0
        print()
    return handoffs


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Play the scripted Puentara (fictional) chat demo")
    parser.add_argument("--ui-lang", choices=["en", "es"], default="en")
    parser.add_argument("--live", action="store_true", help="call Claude (needs ANTHROPIC_API_KEY in .env)")
    parser.add_argument("--record", action="store_true", help="with --live: save answers to fixtures/")
    parser.add_argument("--handoffs", type=Path, default=config.HANDOFFS_FILE, help="handoff file to (re)write")
    args = parser.parse_args(argv)
    ui = args.ui_lang
    try:
        client, model, mode_line, _ = make_client(args.live, ui, record=args.record)
        with open(CONVERSATIONS_FILE, encoding="utf-8") as f:
            conversations = json.load(f)["conversations"]
        print(mode_line)
        store = JsonlStore(args.handoffs)
        store.reset()
        relative = display_path(args.handoffs)
        print(STRINGS[ui]["demo"]["fresh_file"].format(path=relative))
        print()
        count = play(conversations, client, model, ui, store, build_indexes(load_kb()))
    except UserError as error:
        sys.exit(str(error))
    print(STRINGS[ui]["demo"]["footer_one" if count == 1 else "footer"].format(count=count, path=relative))
    if args.record:
        print(t(ui, "recorded").format(count=client.save(), path=config.FIXTURES_FILE.name))
    print(STRINGS[ui]["demo"]["next"])


if __name__ == "__main__":
    main()
