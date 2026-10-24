# Copied from bilingual-reply-assistant (reply_assistant/retrieve.py), not imported across repos.
"""Keyword search over the help articles: a small hand-written BM25.

BM25 scores an article higher when it shares more of the ticket's words, when
those words are rare across the articles (so "card" counts less than
"selfie"), and when the article is not padded with extra text.

Before comparing, both sides are lowercased, accents are removed ("días" =
"dias"), a final plural "s" is dropped ("fees" = "fee") and common EN/ES
words ("the", "de", "mi") are ignored. Only exact word matches count: a
ticket that says "plata" will not find an article that says "dinero".
"""

import math
import re
from collections import Counter

import config

from .language import strip_accents

STOPWORDS = set("""
a an the and or but if so of to in on at by for from with about into as is are was
were be been am do does did have has had i me my mine you your yours we us our it
its this that these those there here what which who when where why how can could
would should will just not no yes please hi hello thanks thank get got still also
very any some all more most than then too again only up out off over after before
el la los las lo un una unos unas y o pero si de del al a en por para con sin sobre
que se me mi mis te tu tus su sus nos le les es son era fue ser estar esta este
esto estoy esta estan hay ya muy mas como cuando donde porque hola gracias favor
tengo tiene hace yo pues eso esa ese cual cuales buenas desde
puedo puedes puede pueden tienen tienes
""".split())
# The last line was added in bilingual-faq-chatbot after the first evaluation run:
# "can" and "have" were already stopwords in English, their Spanish forms were not,
# so "¿Puedo invertir...?" matched the login article ("No puedo iniciar sesión").

WORD_RE = re.compile(r"[a-z0-9]+")
# "[CARD NUMBER MASKED]" is our placeholder, not the customer's words: without
# this, every masked card number would pull up the card articles.
MASK_TOKEN_RE = re.compile(r"\[[A-Z ]+MASKED\]")


def _normalize(word):
    # Drop a final plural "s" ("transfers", "tarjetas"), but not "ss".
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text):
    words = WORD_RE.findall(strip_accents(MASK_TOKEN_RE.sub(" ", text or "")))
    return [_normalize(w) for w in words if w not in STOPWORDS]


# Added once after the first evaluation run (see NOTES.md). Customers use
# everyday words the articles do not; each word on the left also searches for
# the words on the right. English words are listed for Spanish too, because
# mixed tickets ("mi transfer sigue pending") are searched in Spanish.
# Typos are deliberately NOT listed: that would only fit the test set.
SYNONYMS = {
    # card lost or stolen
    "plastic": "card", "wallet": "card lost stolen", "purse": "card lost stolen",
    "misplaced": "lost", "swiped": "stolen",
    "plastico": "tarjeta", "billetera": "tarjeta perdida robada",
    "cartera": "tarjeta perdida robada", "refundio": "perdida", "bajaron": "robaron",
    # login
    "credential": "password", "clave": "contrasena", "ingresar": "iniciar sesion",
    "entrar": "iniciar sesion", "login": "iniciar sesion",
    # identity
    "kyc": "identity verification", "cedula": "documento identidad",
    "pasaporte": "documento identidad",
    # transfers
    "wire": "transfer", "transfer": "transferencia", "pending": "pendiente",
    "plata": "dinero", "mande": "transferencia", "llegado": "llegan",
    # disputes
    "billed": "charged", "double": "twice", "cobraron": "cobro cargo",
    # fees
    "cost": "fee", "quitan": "comision", "descontaron": "comision",
    # tax forms
    "taxe": "tax form", "earned": "1099", "impuesto": "formulario",
    # app problems
    "spin": "loading", "crashe": "crashing", "crash": "crashing", "blanco": "carga",
    # Added in bilingual-faq-chatbot after the first evaluation run: an online order
    # that never arrived is the "item not received" dispute reason.
    "pedido": "producto cargo", "order": "item charge",
}


def expand(words):
    """Add the synonym words for any word that has an entry above."""
    extra = []
    for word in words:
        if word in SYNONYMS:
            extra.extend(SYNONYMS[word].split())
    return words + [_normalize(w) for w in extra]


class Index:
    """BM25 index over one language's articles."""

    def __init__(self, articles, k1=config.BM25_K1, b=config.BM25_B):
        self.articles = list(articles)
        self.k1, self.b = k1, b
        # The title counts twice: it is the best summary of the article.
        self.docs = [Counter(tokenize(f"{a.title} {a.title} {a.body}")) for a in self.articles]
        self.lengths = [sum(doc.values()) for doc in self.docs]
        self.avg_length = sum(self.lengths) / max(len(self.lengths), 1)
        n = len(self.docs)
        doc_freq = Counter(word for doc in self.docs for word in doc)
        # Standard BM25 idf with +1 inside the log so it never goes negative.
        self.idf = {w: math.log(1 + (n - df + 0.5) / (df + 0.5)) for w, df in doc_freq.items()}

    def score(self, query_words, i):
        doc, length = self.docs[i], self.lengths[i]
        total = 0.0
        for word in set(query_words):
            tf = doc.get(word, 0)
            if tf:
                norm = tf + self.k1 * (1 - self.b + self.b * length / self.avg_length)
                total += self.idf[word] * tf * (self.k1 + 1) / norm
        return total

    def search(self, text, top_k=config.SEARCH_TOP_K, min_score=config.SEARCH_MIN_SCORE):
        """Return up to top_k (article, score) pairs, best first, above min_score."""
        words = expand(tokenize(text))
        scored = [(self.articles[i], self.score(words, i)) for i in range(len(self.articles))]
        scored = [(a, s) for a, s in scored if s >= min_score]
        scored.sort(key=lambda pair: (-pair[1], pair[0].id))
        return scored[:top_k]


def build_indexes(kb):
    """One index per language: {"en": Index, "es": Index}."""
    return {lang: Index(articles) for lang, articles in kb.items()}
