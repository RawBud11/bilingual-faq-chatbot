# Copied from bilingual-reply-assistant (reply_assistant/mask.py), not imported across repos.
# Copied from bilingual-ticket-triage (ticket_triage/mask.py), not imported across repos.
"""Mask card numbers, CVVs, one-time codes, passwords after a label, emails and
phone numbers before anything else sees them.

Masked text is what the rules read, what the AI receives and what the handoff
file and agent inbox store. Limit: names, account numbers, IBANs, addresses,
and passwords typed with no label ("Sunflower2024! log me in") are NOT masked.
"""

import re

CARD_MASK = "[CARD NUMBER MASKED]"
CODE_MASK = "[CODE MASKED]"
EMAIL_MASK = "[EMAIL MASKED]"
PHONE_MASK = "[PHONE MASKED]"
PASSWORD_MASK = "[PASSWORD MASKED]"

# 13 to 19 digits, optionally split by spaces, dashes or dots ("0000 1234 ...").
CARD_RE = re.compile(r"(?<!\d)(?:\d[ .-]?){12,18}\d(?!\d)")

# "CVV 123", "cvc: 1234", "código de seguridad 123".
CVV_RE = re.compile(
    r"\b(cvv2?|cvc|security code|c[oó]digo de seguridad)\b(\D{0,12}?)(\d{3,4})(?!\d)",
    re.IGNORECASE,
)

# "code 482913", "código que me llegó es 482913", "PIN 1234", "OTP: 9921",
# and codes typed in two groups: "código 123 456", "code 123-456".
# Conservative on purpose: it can also hide harmless numbers after these words
# (for example "error code 5003"). Hiding too much is safer than too little.
CODE_RE = re.compile(
    r"\b(one[- ]time code|verification code|otp|code|c[oó]digo|clave|pin|passcode|token)\b"
    r"(\D{0,25}?)(\d{3,4}[ -]\d{3,4}|\d{4,8})(?!\d)",
    re.IGNORECASE,
)

# Added in bilingual-faq-chatbot: a password typed
# after a label ("my password is Sunflower2024!", "contraseña: Girasol2024",
# "mi clave es ...", "pw: ..."). Only the next word is hidden. Common words
# after "is" / "es" are left alone, so "my password is wrong" and "mi
# contraseña es incorrecta" stay readable. A password typed with no label is
# NOT masked.
NOT_A_PASSWORD = (
    r"wrong|incorrect|invalid|not|expired|correct|right|too|still|being|blocked|locked|the|a|an|my"
    r"|same|old|new|fine|ok|okay|good|bad|weak|strong|case|different|working|broken|gone|missing"
    r"|required|needed|and|but|or|in|on|for|that|this|it|also|very|already|now|no|never|reset"
    r"|incorrecta|incorrecto|correcta|correcto|invalida|inválida|mala|malo|muy|demasiado|la|el|una"
    r"|un|mi|igual|misma|mismo|bloqueada|vieja|nueva|diferente|otra|corta|larga|segura|debil|débil"
    r"|que|y|o|pero|para|de|en|ya|ahora|tambien|también|nunca"
)
PASSWORD_RE = re.compile(
    r"\b(password|passcode|pass word|pw|pwd|contrase[nñ]a|clave)"
    r"(\s*[:=]\s*|\s+(?:is|es)\s*:?\s*)"
    rf"(?!(?:{NOT_A_PASSWORD})\b)(\S{{3,}})",
    re.IGNORECASE,
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

# Phone numbers need a shape that amounts, dates and ticket numbers do not
# have: an area code in parentheses "(555) 010-0199", or 3-3-4 digit groups
# "555-010-0199", optionally after a country code "+57 300 000 0000".
# With a "+" country code, 2-4-4 groups are accepted too ("+52 55 0000 0000").
# Plain digit runs ("5550100199") are left alone: they could be anything.
# The lookbehind keeps "$1,250.00", "#48213" and "1.250.000" out.
PHONE_RE = re.compile(
    r"(?<![\w$#.,])(?:"
    r"\+\d{1,3}[ .-]?\d{2}[ .-]\d{4}[ .-]\d{4}"
    r"|(?:\+\d{1,3}[ .-]?)?(?:\(\d{3}\)[ .-]?|\d{3}[ .-])\d{3}[ .-]?\d{4}"
    r")(?!\d)"
)


def mask_sensitive(text):
    """Return (masked_text, number_of_items_masked)."""
    count = 0

    def replace_with(mask):
        def replace(_match):
            nonlocal count
            count += 1
            return mask
        return replace

    def keep_label_as(mask):
        def replace(match):
            nonlocal count
            count += 1
            return f"{match.group(1)}{match.group(2)}{mask}"
        return replace

    keep_label = keep_label_as(CODE_MASK)

    # Cards first (longest digit runs), then emails and phones, then codes,
    # so a phone number is masked whole instead of half-eaten by CODE_RE.
    text = CARD_RE.sub(replace_with(CARD_MASK), text or "")
    text = EMAIL_RE.sub(replace_with(EMAIL_MASK), text)
    text = PHONE_RE.sub(replace_with(PHONE_MASK), text)
    text = CVV_RE.sub(keep_label, text)
    # Passwords before codes: "mi clave es 4821" is hidden as a password.
    text = PASSWORD_RE.sub(keep_label_as(PASSWORD_MASK), text)
    text = CODE_RE.sub(keep_label, text)
    return text, count
