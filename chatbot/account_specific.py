"""Spot questions only someone with access to the customer's account can answer.

The chatbot cannot see any account. "What's my balance?", "¿Por qué
rechazaron mi transferencia a Juan?" or "Is my refund approved?" need a
person who can look at the account, so the bot refuses them (without calling
the AI) and offers a person instead.

How it decides: a message is account-specific when it asks about the state of
THIS customer's account (balance, a past transaction, a refund or dispute
decision, why something happened) or asks the bot to change something in it.
General "how do I / where do I / cómo / dónde" questions are NOT
account-specific: "¿Cómo veo mi saldo en la app?" is a how-to question.

Patterns run on lowercase text without accents (see rules.fold), so
"rechazaron" and "rechazáron" match the same way. This is phrase matching,
so new wording can slip through; evaluate.py lists every miss.
"""

import re

from .rules import fold

# "How do I...", "Where can I...", "¿Cómo puedo...?": the customer wants steps,
# not a look at their account. Checked at the start of the message (after an
# optional greeting).
HOW_TO_RE = re.compile(
    r"^\W*(?:(?:hi|hello|hey|hola|buenas|buenos dias|buenas tardes)\W+)?"
    r"(how (do|can|should|would) (i|we|you)|where (do|can|should) (i|we)|is there a way"
    r"|como (puedo|hago|veo|se|reviso|consulto|cambio|cierro)|donde (puedo|veo|encuentro|reviso|consulto)"
    r"|hay (alguna )?forma de)\b"
)

ACCOUNT_ITEMS_EN = r"(account|balance|transfer|payment|refund|dispute|claim|transaction|deposit|card|verification|application)"
ACCOUNT_ITEMS_ES = (r"(cuenta|saldo|transferencia|pago|reembolso|devolucion|disputa|reclamo|movimiento"
                    r"|transaccion|deposito|tarjeta|verificacion|solicitud)")

PATTERNS = [
    # --- English ---------------------------------------------------------
    # Balance and money in the account.
    r"\bmy (current |available )?balance\b",
    r"\bhow much (money )?(do i have|is (left )?in my|have i got)\b",
    # A decision or status about one of their items: "is my refund approved?"
    rf"\b(is|was|has|have|were) my \w*\s?{ACCOUNT_ITEMS_EN}s?\b.{{0,30}}\b(approved|accepted|declined|rejected"
    r"|denied|processed|resolved|closed|cancell?ed|reversed|frozen|blocked|gone through|went through|sent|done)\b",
    rf"\bdid my \w*\s?{ACCOUNT_ITEMS_EN}s?\b.{{0,30}}\b(go through|arrive|clear|get approved|land)\b",
    # "Why was my transfer declined?", "Why did you close my account?"
    rf"\bwhy (was|were|is|did|has|have)\b.{{0,30}}\bmy \w*\s?{ACCOUNT_ITEMS_EN}",
    r"\bwhy did you (charge|close|block|freeze|cancel|decline|reject)\b",
    # "Can you check if my payment to Maria went through?"
    # "verify" / "verificar" were removed after the first evaluation run: "verificar mi
    # cuenta" means identity verification (a help article), not "look at my account".
    rf"\b(check|look up|look at|look into|see|tell me)\b.{{0,20}}\bmy \w*\s?{ACCOUNT_ITEMS_EN}",
    r"\bmy (last|latest|recent|most recent|previous) (transaction|payment|transfer|deposit|charge|purchase)s?\b",
    r"\bwhere is my (refund|money back|reimbursement)\b",
    # Asking the bot to change the account: it cannot.
    r"\b(can|could|would|will) you (please )?(change|update|close|cancel|unlock|unblock|reopen|delete|reset)\b.{0,20}\bmy\b",
    # --- Spanish ---------------------------------------------------------
    r"\b(cual es|cuanto es|cuanto tengo de|dime|ver|revisa|revisar|consulta|consultar|saber) (el |mi )?saldo\b",
    r"\bmi saldo\b",
    r"\bcuanto (dinero |plata )?(tengo|me queda|hay en mi cuenta)\b",
    # "¿Ya aprobaron mi reembolso?", "¿Por qué rechazaron mi transferencia?"
    rf"\b(aprobaron|aceptaron|rechazaron|negaron|procesaron|resolvieron|cerraron|bloquearon|congelaron"
    rf"|cancelaron|devolvieron|enviaron|reversaron)\b.{{0,15}}\b(mi|mis|el|la)\b.{{0,10}}{ACCOUNT_ITEMS_ES}",
    rf"\b(mi|el|la) {ACCOUNT_ITEMS_ES}\b.{{0,20}}\b(ya )?(fue|esta|quedo|salio) (aprobad|rechazad|procesad"
    r"|resuelt|cerrad|bloquead|cancelad|devuelt|enviad)",
    r"\bpor que (me )?(rechazaron|cerraron|bloquearon|cobraron|congelaron|cancelaron|negaron|quitaron)\b",
    rf"\b(revisa|revisas|revisar|ver|consultar|mira|miras|decirme|dime)\b.{{0,20}}\b(mi|mis)\b.{{0,10}}{ACCOUNT_ITEMS_ES}",
    r"\bcuanto me (cobraron|descontaron|quitaron)\b",
    r"\bmi (ultimo|ultima|ultimos|ultimas) (movimiento|transaccion|pago|transferencia|cobro|compra|deposito)",
    r"\bdonde esta mi (reembolso|devolucion|dinero de vuelta)\b",
    # Asking the bot to change the account.
    r"\b(puedes|podrias|pueden|podrian|me puedes|me podrias) (cambiar|actualizar|cerrar|cancelar|desbloquear"
    r"|reactivar|borrar|eliminar|modificar)\b.{0,30}\b(mi|mis)\b",
]
PATTERNS = [re.compile(p) for p in PATTERNS]


def is_how_to(text):
    """True for general how-to questions ("How do I see my balance?")."""
    return bool(HOW_TO_RE.search(fold(text)))


def account_specific_match(text):
    """Return the customer's words that made this account-specific, or ""."""
    folded = fold(text)
    if HOW_TO_RE.search(folded):
        return ""
    for pattern in PATTERNS:
        match = pattern.search(folded)
        if match:
            return text[match.start():match.end()]
    return ""
