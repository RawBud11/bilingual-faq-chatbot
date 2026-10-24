# Copied from bilingual-reply-assistant (tests/test_retrieve.py), not imported across repos.
"""Knowledge base loading and the BM25 keyword search."""

import pytest

import config
from helpers import INDEXES
from chatbot.kb import load_kb, parse_article
from chatbot.retrieve import tokenize


def test_kb_has_eight_pairs_in_both_languages():
    kb = load_kb()
    assert [a.pair for a in kb["en"]] == [a.pair for a in kb["es"]] == [f"{n:02d}" for n in range(1, 9)]
    for en, es in zip(kb["en"], kb["es"]):
        assert en.category == es.category
        assert en.category in config.CATEGORIES
        assert en.id == f"KB-EN-{en.pair}" and es.id == f"KB-ES-{es.pair}"
        assert en.short_answer and en.steps and es.short_answer and es.steps


def test_articles_are_labeled_placeholder():
    for lang, label in (("en", "Placeholder content for the fictional company Puentara"),
                        ("es", "Contenido de ejemplo para la empresa ficticia Puentara")):
        for path in (config.KB_DIR / lang).glob("*.md"):
            assert label in path.read_text(encoding="utf-8"), path.name


def test_parse_article_needs_front_matter():
    with pytest.raises(ValueError):
        parse_article("## Short answer\nHi", source="x.md")
    with pytest.raises(ValueError):
        parse_article("---\nid: KB-EN-99\n---\n## Short answer\nHi", source="x.md")


def test_tokenize_folds_accents_plurals_and_stopwords():
    assert tokenize("Mis transferencias están pendientes desde hace días") == \
        ["transferencia", "pendiente", "dia"]
    assert tokenize("The fees for my transfers") == ["fee", "transfer"]


def test_mask_placeholders_are_not_search_words():
    assert tokenize("My card is [CARD NUMBER MASKED], email [EMAIL MASKED]") == ["card", "email"]


@pytest.mark.parametrize("lang,text,expected", [
    ("en", "My transfer has been pending for 3 days", "KB-EN-04"),
    ("es", "Mi transferencia sigue pendiente", "KB-ES-04"),
    ("en", "How do I dispute a charge?", "KB-EN-05"),
    ("es", "Quiero disputar un cargo", "KB-ES-05"),
    ("en", "Where do I download my 1099-K tax form?", "KB-EN-07"),
    ("es", "¿Dónde descargo mi formulario de impuestos?", "KB-ES-07"),
    ("en", "My identity verification selfie was rejected", "KB-EN-03"),
    ("es", "La app no carga", "KB-ES-08"),
])
def test_finds_the_right_article_first(lang, text, expected):
    found = INDEXES[lang].search(text)
    assert found[0][0].id == expected


def test_returns_at_most_two_best_first_above_threshold():
    found = INDEXES["en"].search("transfer pending fee international card")
    assert 1 <= len(found) <= config.SEARCH_TOP_K
    scores = [score for _, score in found]
    assert scores == sorted(scores, reverse=True)
    assert all(score >= config.SEARCH_MIN_SCORE for score in scores)


@pytest.mark.parametrize("lang,text", [("es", "¿Cuál es el horario de atención?"),
                                       ("en", "Do you have a referral program?")])
def test_no_article_when_nothing_matches(lang, text):
    assert INDEXES[lang].search(text) == []


def test_spanish_index_only_returns_spanish_articles():
    found = INDEXES["es"].search("transferencia comisión tarjeta")
    assert found and all(a.id.startswith("KB-ES-") for a, _ in found)


@pytest.mark.parametrize("lang,text,expected", [
    ("es", "la plata no ha llegado", "KB-ES-04"),        # plata -> dinero, llegado -> llegan
    ("es", "mi transfer sigue pending", "KB-ES-04"),     # English words in a Spanish search
    ("en", "Misplaced my plastic, what now?", "KB-EN-01"),
])
def test_synonyms_help_everyday_words(lang, text, expected):
    found = INDEXES[lang].search(text)
    assert found and found[0][0].id == expected
