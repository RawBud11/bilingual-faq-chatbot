# Copied from bilingual-reply-assistant (reply_assistant/language.py), not imported across repos.
# Copied from bilingual-ticket-triage (ticket_triage/language.py), not imported across repos.
"""Detect whether a ticket is in English, Spanish, both, or neither.

Plain Python, no extra library: count common English and Spanish words, and
give Spanish a point for each word with an accent, ñ, ¿ or ¡.
Words that exist in both languages ("no", "me", "a") are left out on purpose.
"""

import re
import unicodedata

EN_WORDS = set("""
the and is are was were my i you your it its to of in for on with this that
have has had not cant can't dont don't didnt didn't doesnt doesn't wont won't
why what how when where do does did be been please thanks thank help hi hello
card account money charge charged payment transfer still yet never again from
at but there they we will would can get got know just an if or so after since
also need want which any all some it's im i'm sent pending login password
""".split())

ES_WORDS = set("""
el la los las del que y en un una es mi mis por para con se lo le su al pero
como cuando donde porque ya sin hay yo tu tengo puedo quiero necesito ayuda
tarjeta cuenta dinero cobro cargo pago transferencia gracias hola favor sigue
desde todavia nunca otra vez esta este estoy son fue muy mas hace dice pasa
dias cuanto cual tienen llega llego robaron perdi contrasena hicieron pedi
""".split())

SPANISH_MARKS = set("áéíóúñ¿¡")
WORD_RE = re.compile(r"[a-z']+")


def strip_accents(text):
    """Lowercase and remove accents, so 'Contraseña' and 'contrasena' match."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def language_scores(text):
    """Return (english_score, spanish_score) for a piece of text."""
    words = WORD_RE.findall(strip_accents(text))
    en = sum(1 for w in words if w in EN_WORDS)
    es = sum(1 for w in words if w in ES_WORDS)
    es += sum(1 for w in text.lower().split() if any(ch in SPANISH_MARKS for ch in w))
    return en, es


def detect_language(text):
    """Return 'en', 'es', 'mixed' or 'other'."""
    en, es = language_scores(text)
    if en == 0 and es == 0:
        return "other"
    # Mixed only when both languages are really there, not one borrowed word
    # like "me hicieron un charge" (that is Spanish with an English noun).
    if min(en, es) >= 2 and min(en, es) / max(en, es) >= 0.5:
        return "mixed"
    if en == es:
        return "mixed"
    return "en" if en > es else "es"
