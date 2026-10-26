"""HTML for the read-only agent inbox (/agent) and the help article pages (/kb/<id>).

Every value from a handoff record or an article goes through html.escape:
customers type whatever they want, and a message like "<script>" must show
up as text, not run in the agent's browser. There is no <form> anywhere:
this inbox only shows handoffs, agents reply from their real helpdesk.
"""

from html import escape

from .handoff import URGENCY_ORDER
from .strings import STRINGS


def _page(title, lang, body):
    return (f'<!DOCTYPE html>\n<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{escape(title)}</title>\n<link rel="stylesheet" href="/pages.css">\n</head>\n'
            f'<body>\n{body}\n</body>\n</html>\n')


def _label(table, key):
    """Look up a label; unknown values (a hand-edited file) are shown as typed."""
    return table.get(key, str(key))


def _sort_key(record):
    urgency = record.get("urgency")
    rank = URGENCY_ORDER.index(urgency) if urgency in URGENCY_ORDER else 0
    return (-rank, str(record.get("id", "")))


def render_inbox(records, lang, path_label):
    s = STRINGS[lang]
    labels = s["inbox"]
    other = "es" if lang == "en" else "en"
    parts = [f'<header><h1>{escape(labels["title"])}</h1>',
             f'<p class="banner">{escape(labels["banner"])}</p>',
             f'<p><a href="/agent?lang={other}">{escape(labels["switch"])}</a></p></header>',
             "<main>"]
    if not records:
        parts.append(f'<p class="empty">{escape(labels["empty"])}</p>')
    else:
        parts.append(f'<p>{escape(labels["count_one" if len(records) == 1 else "count"].format(count=len(records), path=path_label))}</p>')
    for record in sorted(records, key=_sort_key):
        urgency = str(record.get("urgency", ""))
        summary = record.get("summary")
        summary = summary.get(lang, "") if isinstance(summary, dict) else str(summary or "")
        rows = [
            (labels["time"], record.get("time", "")),
            (labels["urgency"], _label(s["urgency"], urgency)),
            (labels["category"], _label(s["categories"], record.get("category", ""))),
            (labels["language"], _label(s["languages"], record.get("language", ""))),
            (labels["trigger"], _label(s["triggers"], record.get("trigger", ""))),
            (labels["summary"], summary),
        ]
        css_class = escape(urgency if urgency in URGENCY_ORDER else "normal")
        parts.append(f'<article class="handoff {css_class}">')
        parts.append(f'<h2>{escape(str(record.get("id", "")))}</h2><dl>')
        for name, value in rows:
            parts.append(f"<dt>{escape(name)}</dt><dd>{escape(str(value))}</dd>")
        parts.append(f'</dl><h3>{escape(labels["transcript"])}</h3><ol class="transcript">')
        transcript = record.get("transcript")
        for entry in transcript if isinstance(transcript, list) else []:
            if not isinstance(entry, dict):
                continue
            role = "bot" if entry.get("role") == "bot" else "customer"
            parts.append(f'<li class="{role}"><strong>{escape(labels[role])}:</strong> '
                         f'{escape(str(entry.get("text", "")))}</li>')
        parts.append("</ol></article>")
    parts.append("</main>")
    return _page(labels["title"], lang, "\n".join(parts))


def render_article(article, lang):
    """One help article as plain HTML: '## ' lines become headings."""
    labels = STRINGS[lang]["article"]
    if article is None:
        return _page(labels["missing"], lang,
                     f'<main><p>{escape(labels["missing"])}</p><p><a href="/">{escape(labels["back"])}</a></p></main>')
    lines = []
    for line in article.body.splitlines():
        if line.startswith("## "):
            lines.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("> "):
            lines.append(f'<p class="banner">{escape(line[2:])}</p>')
        elif line.strip():
            lines.append(f"<p>{escape(line)}</p>")
    body = (f'<header><p class="banner">{escape(labels["label"])}</p>'
            f'<h1>{escape(article.title)}</h1><p class="article-id">{escape(article.id)}</p></header>'
            f'<main>{"".join(lines)}<p><a href="/">{escape(labels["back"])}</a></p></main>')
    return _page(article.title, lang, body)
