# Copied from bilingual-reply-assistant (reply_assistant/kb.py), not imported across repos.
"""Load the help articles from kb/en/*.md and kb/es/*.md.

Each file starts with a small front matter block (id, pair, lang, category,
title) between two "---" lines, then a "Short answer" section and a "Steps"
section ("Respuesta corta" and "Pasos" in Spanish). Plain parsing, no YAML
library: every front matter line is "key: value".
"""

from dataclasses import dataclass
from pathlib import Path

import config

SHORT_ANSWER_HEADINGS = {"short answer", "respuesta corta"}
STEPS_HEADINGS = {"steps", "pasos"}


@dataclass
class Article:
    id: str          # "KB-ES-04"
    pair: str        # "04": the same topic in both languages
    lang: str        # "en" or "es"
    category: str
    title: str
    short_answer: str
    steps: str
    body: str        # everything after the front matter (what search reads)


def parse_article(text, source="article"):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---" or "---" not in [l.strip() for l in lines[1:]]:
        raise ValueError(f"{source}: missing front matter between '---' lines")
    end = 1 + [l.strip() for l in lines[1:]].index("---")
    meta = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    missing = {"id", "pair", "lang", "category", "title"} - meta.keys()
    if missing:
        raise ValueError(f"{source}: front matter is missing {', '.join(sorted(missing))}")

    sections, current = {}, None
    for line in lines[end + 1:]:
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)

    def section(names):
        for name in names:
            if name in sections:
                return "\n".join(sections[name]).strip()
        return ""

    return Article(
        id=meta["id"], pair=meta["pair"].zfill(2), lang=meta["lang"],
        category=meta["category"], title=meta["title"],
        short_answer=section(SHORT_ANSWER_HEADINGS), steps=section(STEPS_HEADINGS),
        body="\n".join(lines[end + 1:]).strip(),
    )


def load_kb(kb_dir=config.KB_DIR):
    """Return {"en": [Article, ...], "es": [...]}, sorted by id."""
    kb = {"en": [], "es": []}
    for path in sorted(Path(kb_dir).glob("*/*.md")):
        article = parse_article(path.read_text(encoding="utf-8"), source=path.name)
        kb.setdefault(article.lang, []).append(article)
    for articles in kb.values():
        articles.sort(key=lambda a: a.id)
    return kb
