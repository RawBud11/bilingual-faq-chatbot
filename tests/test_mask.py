# Copied from bilingual-reply-assistant (tests/test_mask.py), not imported across repos.
# Copied from bilingual-ticket-triage (tests/test_mask.py); email and phone tests added at the end.
import re

import pytest

from chatbot.mask import CARD_MASK, CODE_MASK, mask_sensitive


@pytest.mark.parametrize("text", [
    "My card number is 0000123456789012, please block it.",
    "My card number is 0000 1234 5678 9012, please block it.",
    "Mi tarjeta es 0000-1234-5678-9012, bloquéenla por favor.",
])
def test_masks_card_numbers(text):
    masked, count = mask_sensitive(text)
    assert CARD_MASK in masked
    assert count == 1
    assert not re.search(r"\d{4}", masked)


@pytest.mark.parametrize("text,secret", [
    ("Someone used my card, CVV 123", "123"),
    ("el cvv: 4821 por si lo necesitas", "4821"),
    ("Mi código de seguridad es 907", "907"),
    ("I got a code 482913 I never asked for", "482913"),
    ("Me llegó el código 482913 por SMS", "482913"),
    ("el codigo que me llego es 553201", "553201"),
    ("my PIN is 1234", "1234"),
    ("OTP: 99210", "99210"),
])
def test_masks_cvv_and_codes(text, secret):
    masked, count = mask_sensitive(text)
    assert secret not in masked
    assert CODE_MASK in masked
    assert count == 1


def test_masks_card_and_cvv_together_en_es():
    en, n_en = mask_sensitive("My card is 0000 1043 3218 1960, CVV 529.")
    es, n_es = mask_sensitive("Mi tarjeta es 0000104332181960 y el CVV 529.")
    assert n_en == 2 and n_es == 2
    assert "529" not in en and "529" not in es


@pytest.mark.parametrize("text", [
    "I sent $139.85 on Oct 15 and it says failed.",
    "¿Dónde descargo mi formulario 1099 del 2025?",
    "My transfer of $1,250.00 is pending since 2026-10-03.",
    "Termina en 4821.",  # last 4 digits alone are fine to keep
])
def test_leaves_normal_numbers_alone(text):
    masked, count = mask_sensitive(text)
    assert masked == text
    assert count == 0


def test_empty_text():
    assert mask_sensitive("") == ("", 0)
    assert mask_sensitive(None) == ("", 0)


@pytest.mark.parametrize("text", [
    "card 0000.1111.2222.3333 not working",
    "mi tarjeta 0000.1111.2222.3333 no funciona",
])
def test_masks_card_numbers_with_dots(text):
    masked, count = mask_sensitive(text)
    assert CARD_MASK in masked and count == 1
    assert "1111" not in masked


@pytest.mark.parametrize("text,secret", [
    ("mi código es 123 456, no me deja entrar", "123 456"),
    ("el codigo: 123-456", "123-456"),
    ("my code is 123 456", "123 456"),
    ("verification code 1234-5678", "1234-5678"),
])
def test_masks_codes_typed_in_two_groups(text, secret):
    masked, count = mask_sensitive(text)
    assert secret not in masked
    assert CODE_MASK in masked and count == 1


# --- Emails and phone numbers ---------------------------------------------------

from chatbot.mask import EMAIL_MASK, PHONE_MASK  # noqa: E402


@pytest.mark.parametrize("text,secret", [
    ("Hola, mi correo es cliente.demo42@example.com y no me llega nada.", "cliente.demo42@example.com"),
    ("My email is customer.demo07+puentara@example.com", "customer.demo07+puentara@example.com"),
])
def test_masks_emails_en_es(text, secret):
    masked, count = mask_sensitive(text)
    assert secret not in masked
    assert EMAIL_MASK in masked and count == 1


@pytest.mark.parametrize("text,secret", [
    ("Call me at (555) 010-0199 please.", "(555) 010-0199"),
    ("my phone is 555-010-0142", "555-010-0142"),
    ("Mi celular es +57 300 000 0000, llámame.", "+57 300 000 0000"),
    ("Escríbeme al +52 55 0000 0000", "+52 55 0000 0000"),
    ("Call +1 (555) 010-0199", "+1 (555) 010-0199"),
])
def test_masks_us_and_latam_phones(text, secret):
    masked, count = mask_sensitive(text)
    assert secret not in masked
    assert PHONE_MASK in masked and count == 1


@pytest.mark.parametrize("text", [
    "I sent $1,250.00 on 2026-10-12 and it is still pending.",
    "Envié 1.250.000 COP el 2026-10-12 y no ha llegado.",
    "This is about ticket #48213, opened 2026-10-12.",
    "Es sobre el ticket #48213 del 12/10/2026.",
    "Transfer TR-2026-104433 of $300.00",
])
def test_phone_and_email_masks_leave_amounts_dates_and_ticket_numbers(text):
    masked, count = mask_sensitive(text)
    assert masked == text
    assert count == 0


def test_card_email_and_phone_in_one_ticket():
    text = "Card 0000 1111 2222 3333, email cliente.demo42@example.com, phone (555) 010-0199, CVV 123"
    masked, count = mask_sensitive(text)
    assert count == 4
    for secret in ("1111", "cliente.demo42", "010-0199", "123"):
        assert secret not in masked


# --- Passwords after a label (added in bilingual-faq-chatbot) ----------------------

from chatbot.mask import PASSWORD_MASK  # noqa: E402


@pytest.mark.parametrize("text,secret", [
    ("My password is Sunflower2024! please log me in", "Sunflower2024"),
    ("mi contraseña es Girasol2024, ayúdame a entrar", "Girasol2024"),
    ("password: hunter22", "hunter22"),
    ("Contraseña: Perro.99 y no entra", "Perro.99"),
    ("pw: abc123", "abc123"),
    ("mi clave es 4821", "4821"),
    ("clave: Luna#7", "Luna#7"),
])
def test_masks_passwords_after_a_label_en_es(text, secret):
    masked, count = mask_sensitive(text)
    assert secret not in masked
    assert PASSWORD_MASK in masked and count == 1


@pytest.mark.parametrize("text", [
    "My password is wrong and I can't log in",
    "The password is not working",
    "Mi contraseña es incorrecta",
    "mi contraseña es muy larga",
    "How do I reset my password?",
    "Olvidé mi contraseña, ¿cómo la cambio?",
])
def test_password_words_without_a_password_are_left_alone(text):
    assert mask_sensitive(text) == (text, 0)
