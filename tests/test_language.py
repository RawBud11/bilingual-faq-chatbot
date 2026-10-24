# Copied from bilingual-reply-assistant (tests/test_language.py), not imported across repos.
# Copied from bilingual-ticket-triage (tests/test_language.py).
import pytest

from chatbot.language import detect_language

CASES = [
    ("My card was stolen this morning, please block it.", "en"),
    ("I forgot my password and the reset email never arrives.", "en"),
    ("help", "en"),
    ("transfer stuck", "en"),
    ("UNAUTHORIZED CHARGE ON MY ACCOUNT $410.83!!!", "en"),
    ("Why was I charged a fee on Oct 15?", "en"),
    ("Me robaron la tarjeta en el metro, ¿qué hago?", "es"),
    ("Olvidé mi contraseña y no me llega el correo.", "es"),
    ("olvide mi contrasena y no me llega el correo", "es"),  # no accents
    ("ayuda", "es"),
    ("TARJETA ROBADA, BLOQUÉENLA POR FAVOR", "es"),
    ("¿Cuánto cuesta enviar dinero a Colombia?", "es"),
    ("la app se congela en Ajustes", "es"),
    ("me hicieron un charge que no reconozco", "es"),  # Spanglish, mostly Spanish
    ("mi transfer está pending desde el lunes", "es"),
    ("Hi, tengo un problema with my card", "mixed"),
    ("My transfer is pending. Otra cosa, ¿dónde está mi formulario?", "mixed"),
    ("Bonjour, je n'arrive pas à recevoir mon code. Merci.", "other"),
    ("1099?", "other"),
    ("ok", "other"),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_detect_language(text, expected):
    assert detect_language(text) == expected
