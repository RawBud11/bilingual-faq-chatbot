# Copied from bilingual-reply-assistant (tests/test_rules.py), not imported across repos.
# Copied from bilingual-ticket-triage (tests/test_rules.py).
import pytest

from chatbot.rules import apply_rules, higher_urgency


@pytest.mark.parametrize("text,category,floor,fraud", [
    ("Someone changed the email on my account", "account_access", "urgent", True),
    ("alguien cambió el correo de mi cuenta", "account_access", "urgent", True),
    ("me hackearon la cuenta", "account_access", "urgent", True),
    ("My wallet was stolen with my card inside", "card_lost_stolen", "urgent", True),
    ("se me perdio la tarjeta en el taxi", "card_lost_stolen", "urgent", True),
    ("I don't recognize this charge", "charge_dispute", "urgent", True),
    ("me hicieron un charge que no reconozco", "charge_dispute", "urgent", True),
    ("I was charged twice by the store", "charge_dispute", "high", False),
    ("Quiero disputar un cargo", "charge_dispute", "high", False),
    ("Where is my W-8BEN?", "tax_forms", None, False),
    ("¿Dónde descargo mi formulario 1099?", "tax_forms", None, False),
    ("NO PUEDO INICIAR SESIÓN", "account_access", None, False),
    ("La app se cierra cada vez", "app_bug", None, False),
])
def test_clear_cases_decided_by_rules(text, category, floor, fraud):
    result = apply_rules(text)
    assert result.category == category
    assert result.floor == floor
    assert result.fraud is fraud
    assert result.matched


def test_urgent_rule_wins_over_other_topics():
    result = apply_rules("Card stolen. Also, the app crashed twice today.")
    assert result.category == "card_lost_stolen"


def test_two_topics_go_to_ai_with_floor():
    result = apply_rules("I want a refund. Also, where is my 1099?")
    assert result.category is None
    assert result.floor == "high"
    assert set(result.candidates) == {"charge_dispute", "tax_forms"}


@pytest.mark.parametrize("text", ["Do you have a plan for small teams?",
                                  "¿Cuál es el horario de atención?"])
def test_general_questions_go_to_ai(text):
    assert apply_rules(text).category is None


def test_higher_urgency():
    assert higher_urgency("low", "urgent") == "urgent"
    assert higher_urgency("high", None) == "high"
    assert higher_urgency(None, "normal") == "normal"


def test_evidence_quotes_the_customers_own_words():
    result = apply_rules("Me llegó un código [CODE MASKED] que no pedí y no puedo entrar")
    assert result.matched == "código [CODE MASKED] que no pedí"
    assert apply_rules("TARJETA ROBADA").matched == "TARJETA ROBADA"


@pytest.mark.parametrize("text", [
    "I lost my phone charger, do you sell them?",
    "The payment didn't make it to my landlord yet.",
    "I never made it to the branch yesterday.",
    "¿Se puede pagar sin autorización previa del banco?",
    "I cloned the repo from your developer docs.",
])
def test_innocent_phrases_are_not_fraud(text):
    result = apply_rules(text)
    assert result.floor != "urgent"
    assert not result.fraud


@pytest.mark.parametrize("text", [
    "I didn't make this payment.",
    "My card was cloned at an ATM.",
    "Me clonaron la tarjeta.",
    "Me cobraron sin mi autorización.",
    "I lost my phone and the app is still logged in.",
])
def test_real_fraud_phrases_still_urgent(text):
    result = apply_rules(text)
    assert result.floor == "urgent" and result.fraud
