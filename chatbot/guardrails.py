# Copied from bilingual-reply-assistant (reply_assistant/guardrails.py), not imported across repos.
"""Check every draft before an agent sees it as "ready", in English and Spanish.

Two checks:
1. asks_sensitive: the draft asks the customer for a card number, PIN, CVV,
   password or one-time code. "We never ask for your CVV" is fine.
2. promises_outcome: the draft promises a refund or a dispute result.
   "We can't guarantee a refund" is fine.

How it decides, in plain words:
- A sentence is flagged when it has a request ("send us", "envíanos",
  "reply with", "what is") AND a sensitive item ("CVV", "código") anywhere in it.
- A request does not count when a negation word ("never", "don't", "no",
  "nunca", "nadie") comes before it in the same comma-separated part. So
  "never share your PIN" passes, but "Don't worry, just send your PIN" is
  flagged: the "don't" belongs to "worry", not to "send".
- A promise only counts as negated when the negation sits right before it:
  "we cannot guarantee", "no te podemos prometer". "No te preocupes que te
  devolveremos tu dinero" is still a promise.
- A promise after a real condition ("if a refund is approved...", "si se
  aprueba...") is not flagged. "Once" and "cuando" are not conditions:
  "we will refund you once the review is done" is a promise.

This is phrase matching: a safety net, not a guarantee. Every draft still
needs a person to read it.
"""

import re

from .rules import fold  # lowercase, no accents, same length as the input

SENTENCE_RE = re.compile(r"[^.!?\n¿¡]+")
# Comma-separated parts inside a sentence; "but" / "pero" also start a new part.
PART_RE = re.compile(r"(?:(?!\b(?:but|however|pero|aunque)\b)[^,;:()])+")

NEGATION_RE = re.compile(
    r"\b(never|not|no|nobody|no one|don'?t|won'?t|can'?t|cannot|nunca|jamas|nadie|ni)\b")

# A negation that governs the promise: it must end right before the promise
# words ("cannot guarantee", "no podemos garantizar", "no te podemos prometer").
PROMISE_NEGATION_RE = re.compile(
    r"\b(can'?t|cannot|can not|won'?t|will not|unable to|not able to|do not|don'?t|never"
    r"|no (te |le |les )?(podemos|puedo|se puede|vamos a|garantizamos|prometemos)"
    r"( asegurar(te)?( que)?)?|nunca|(can'?t|cannot|can not) (assure|ensure) you( that)?)\s+$")
PROMISE_VERB_RE = re.compile(r"promise|guarantee|promet|garantiz")
# Right before a promise VERB, a bare "no" also negates it: "no garantizamos",
# "no te prometemos", "no es posible garantizar", "there is no guarantee".
# Only for these verbs: "No worries we will refund you" is still a promise.
VERB_NEGATION_RE = re.compile(r"\b(no( te| le| les)?|no es posible|not possible to)\s+$")

# Checked on the original text (lowercase, accents kept), so "sí" (yes) is
# not read as "si" (if).
CONDITION_RE = re.compile(r"\b(if|unless|si|en caso de)\b")

# "send" etc. do not count after "we", "will" or "the app"... ("we'll send
# you a new code" is us sending, not a request). Same for "te envía".
REQUEST_RE = re.compile(
    r"(?<!we )(?<!we'll )(?<!will )(?<!i'll )(?<!app )"
    r"\b(send|share|provide|give|tell|type|write|confirm|include)\b"
    r"|\b(text|read|email) (us|me)\b"
    r"|\breply (to us |to this message )?with\b|\blet us know\b|\bwhat(?: is|'s| are)\b"
    r"|\b(we|i) (need|require)\b|\bask(ing)? (you |me |us )?for\b"
    r"|(?<!te )(?<!le )(?<!se )\b(envia|envianos|enviame|enviarnos|manda|mandanos|mandame)\b"
    r"|\b(comparte|compartenos|compartir|compartirnos|dinos|dime|indicanos|indica"
    r"|escribenos|confirma|confirmanos|confirmas|confirmes|respondenos|danos|dame|dar|darnos"
    r"|proporciona|proporcionanos|pasanos|necesitamos|necesito|requerimos"
    # tú forms ("si nos envías tu CVV", "¿nos compartes...?", "escribe aquí...")
    # and "pídeme" / "pídenos". Plain "pide" is left out on purpose, see below.
    r"|envias|mandas|compartes|das|pasas|escribes|escribe|pideme|pidenos)\b"
    # "pedir" only counts when aimed at the customer ("te pediremos tu PIN");
    # "pide un código nuevo" tells the customer to request one in the app.
    r"|\b(te|le) (vamos a pedir|pediremos|pedimos|pide|pedira|pediran|pidamos"
    r"|solicitamos|solicitaremos)\b"
    r"|\bcual es\b"
)

# The last 4 digits are commonly used to identify a card and are fine to ask.
LAST_FOUR_RE = re.compile(
    r"\b(last (4|four)|ultimos (4|cuatro)) (digits|digitos)( of| de)?( your| the| tu| la)?"
    r"( card number| card| tarjeta)?")

SENSITIVE_RE = re.compile(
    r"\b(full |whole |complete )?card numbers?\b|\bnumbers? (on|of|from) (the front of )?(your|the) card\b"
    r"|\b1[3-9][- ]digit|\bpin\b|\bcvv2?\b|\bcvc\b|\bsecurity code\b|\b(3|three) digits\b"
    r"|\bdigits on the back\b|\bpasswords?\b|\bpasscodes?\b|\bcodes?\b|\botp\b"
    r"|\bnumeros? (completo )?de (tu |la )?tarjeta\b|\bcodigos?\b|\bclave\b|\bcontrasena\b"
    r"|\b(tres|3) digitos\b|\bdigitos de (atras|detras|el reverso|la parte de atras)\b"
    r"|\bcard details\b|\bdatos de (tu|la) tarjeta\b"
)

PROMISE_RE = re.compile(
    r"\byou('ll| will) (definitely |surely |certainly |absolutely )?(get|receive|have) "
    r"(your |the |all )?(money|refund|funds|it)\b"
    r"|\b(we|we'll|we will|we're going to|we are going to) (definitely |surely |certainly )?"
    r"(refund|reimburse|return the money|give you back|give back)\b"
    r"|\bguarantee|\bpromise\b|\bwill be (refunded|returned|reimbursed|reversed|credited back)\b"
    r"|\b(resolved|decided) in your favou?r\b|\bget (your money|it|the money) back\b"
    r"|\b(devolveremos|devolvemos|reembolsaremos|reembolsamos|reintegraremos|reintegramos)\b"
    r"|\b(vamos|van) a (devolver|reembolsar|reintegrar)\b|\bgarantiz|\bpromet"
    r"|\b(vas|va) a (recibir|recuperar|tener) (tu|el|todo|la)\b|\brecibiras (tu|el)\b"
    r"|\brecuperaras\b|\ba tu favor\b"
)


def _parts(sentence, offset):
    for part in PART_RE.finditer(sentence):
        yield part.start() + offset, part.group(0)


def _negated(part_text, position_in_part):
    """True when a negation word comes before `position_in_part` in this part."""
    return bool(NEGATION_RE.search(part_text[:position_in_part]))


def _promise_in(part_folded, part_original):
    """True when this part promises an outcome (see the module docstring)."""
    for promise in PROMISE_RE.finditer(part_folded):
        before = part_folded[:promise.start()]
        is_verb = bool(PROMISE_VERB_RE.search(promise.group(0)))
        if PROMISE_NEGATION_RE.search(before) or (is_verb and VERB_NEGATION_RE.search(before)):
            if is_verb:
                return False  # "can't promise X": X is not promised either
            continue
        if CONDITION_RE.search(part_original[:promise.start()].lower()):
            continue
        return True
    return False


def check_draft(text):
    """Return a list of findings: [{"kind": ..., "match": original words}].

    An empty list means the draft passed both checks.
    """
    text = text or ""
    folded = fold(text).replace("’", "'")
    findings = []
    for sentence in SENTENCE_RE.finditer(folded):
        s_text, s_start = sentence.group(0), sentence.start()
        clean = LAST_FOUR_RE.sub(lambda m: " " * len(m.group(0)), s_text)
        sensitive = SENSITIVE_RE.search(clean)
        for p_start, p_text in _parts(clean, s_start):
            if sensitive:
                for request in REQUEST_RE.finditer(p_text):
                    if not _negated(p_text, request.start()):
                        findings.append({"kind": "asks_sensitive",
                                         "match": text[s_start:s_start + len(s_text)].strip()})
                        break
            original = text[p_start:p_start + len(p_text)]
            if _promise_in(p_text, original):
                findings.append({"kind": "promises_outcome", "match": original.strip()})
    # One finding per kind and quote is enough.
    unique = []
    for finding in findings:
        if finding not in unique:
            unique.append(finding)
    return unique


def label(text):
    """One label for evaluation: "asks_sensitive", "promises_outcome" or "ok"."""
    kinds = {f["kind"] for f in check_draft(text)}
    if "asks_sensitive" in kinds:
        return "asks_sensitive"
    if "promises_outcome" in kinds:
        return "promises_outcome"
    return "ok"
