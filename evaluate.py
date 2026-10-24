"""Measure what the chatbot does with labeled synthetic messages.

Usage:
  python evaluate.py
  python evaluate.py --ui-lang es
  python evaluate.py --save docs/eval_first_run.txt   (used once, for the first run)

Files:
  data/chat_labeled.csv  ~75 EN/ES messages with the expected action, written
                         before account_specific.py (one tuning round after)
  data/chat_fresh.csv    written after tuning, never tuned on

Expected actions: answer:<article pair>, handoff_urgent, handoff_requested,
refuse_account, no_answer, sensitive_warning. Each message is one new chat
(no history). The AI is never called and nothing is written to disk except
--save. Every miss is listed, so the numbers can be checked by hand.
All data is synthetic (fictional Puentara).
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import config
from chatbot.ai import TemplateOnlyClient
from chatbot.handoff import MemoryStore
from chatbot.kb import load_kb
from chatbot.retrieve import build_indexes
from chatbot.strings import STRINGS
from chatbot.turn import run_turn

LABELED_FILE = config.DATA_DIR / "chat_labeled.csv"
FRESH_FILE = config.DATA_DIR / "chat_fresh.csv"
ACTION_ORDER = ["answer", "handoff_urgent", "handoff_requested", "refuse_account", "no_answer",
                "sensitive_warning"]
HANDOFF_OR_REFUSE = {"handoff_urgent", "handoff_requested", "handoff_two_misses", "refuse_account"}

# The blind first run, before the one tuning round (full output:
# docs/eval_first_run.txt). Printed next to the current numbers so a tuned
# result is never read as a blind one.
FIRST_RUN = {"overall": (70, 76), "paraphrase": (42, 46), "false_handoffs": (1, 37),
             "wrong_answers": (0, 11), "urgent_answered": (0, 10)}


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [row for row in csv.DictReader(f) if row.get("message")]


def got_label(result):
    if result["action"] == "answer":
        return f'answer:{result["source"]["id"][-2:]}'
    return result["action"]


def run(rows, indexes):
    client = TemplateOnlyClient()
    results = []
    for row in rows:
        result = run_turn(row["message"], [], client=client, indexes=indexes, store=MemoryStore())
        results.append((row, got_label(result)))
    return results


def pct(hits, total):
    return f"{hits / total:.0%}" if total else "n/a"


def summarize(results):
    by_action = defaultdict(lambda: [0, 0])
    for row, got in results:
        action = row["expected"].split(":")[0]
        by_action[action][1] += 1
        by_action[action][0] += got == row["expected"]
    para = [(r, g) for r, g in results if r["kind"] == "paraphrase"]
    return {
        "by_action": by_action,
        "overall": (sum(g == r["expected"] for r, g in results), len(results)),
        "paraphrase": (sum(g == r["expected"] for r, g in para), len(para)),
        "false_handoffs": (sum(g in HANDOFF_OR_REFUSE for r, g in results if r["expected"].startswith("answer")),
                           sum(r["expected"].startswith("answer") for r, _ in results)),
        "wrong_answers": (sum(g.startswith("answer") for r, g in results if r["expected"] == "refuse_account"),
                          sum(r["expected"] == "refuse_account" for r, _ in results)),
        "urgent_answered": (sum(g.startswith("answer") for r, g in results if r["expected"] == "handoff_urgent"),
                            sum(r["expected"] == "handoff_urgent" for r, _ in results)),
    }


def report(ui, indexes):
    e = STRINGS[ui]["eval"]
    out = [e["header"], e["about"], e["tuned_note"], ""]
    rows = read_csv(LABELED_FILE)
    results = run(rows, indexes)
    s = summarize(results)

    def with_first(key, value):
        if key in FIRST_RUN:
            hits, total = FIRST_RUN[key]
            return f'{value} | {e["first_run_note"].format(value=f"{hits}/{total} ({pct(hits, total)})")}'
        return value

    out.append(e["file"].format(path=LABELED_FILE.relative_to(config.PROJECT_DIR).as_posix(), count=len(rows)))
    out.append(e["recall_title"])
    for action in ACTION_ORDER:
        hits, total = s["by_action"].get(action, (0, 0))
        out.append(e["recall_line"].format(action=action, hits=hits, total=total, pct=pct(hits, total)))
    hits, total = s["overall"]
    out.append(with_first("overall", f'{e["overall"]}: {hits}/{total} ({pct(hits, total)})'))
    hits, total = s["paraphrase"]
    out.append(with_first("paraphrase", f'  paraphrase: {hits}/{total} ({pct(hits, total)})'))
    for key in ("false_handoffs", "wrong_answers", "urgent_answered"):
        hits, total = s[key]
        out.append(with_first(key, f"{e[key]}: {hits}/{total}"))

    fresh = read_csv(FRESH_FILE) if FRESH_FILE.exists() else []
    if fresh:
        hits, total = summarize(run(fresh, indexes))["overall"]
        out.append(f'{e["fresh"]}: {hits}/{total} ({pct(hits, total)})')
    else:
        out.append(e["fresh_empty"])

    out.append("")
    out.append(e["misses"])
    misses = [(r, g) for r, g in results if g != r["expected"]]
    for row, got in misses:
        out.append(f'  {row["id"]} [{row["lang"]}, {row["kind"]}] {row["expected"]} -> {got}: {row["message"]}')
    if not misses:
        out.append(e["no_misses"])
    return out


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Evaluate the chatbot on labeled synthetic messages")
    parser.add_argument("--ui-lang", choices=["en", "es"], default="en")
    parser.add_argument("--save", type=Path, help="also write this run to a text file")
    args = parser.parse_args(argv)
    lines = report(args.ui_lang, build_indexes(load_kb()))
    print("\n".join(lines))
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(STRINGS[args.ui_lang]["eval"]["saved"].format(path=args.save))


if __name__ == "__main__":
    main()
