# Copied from bilingual-reply-assistant (reply_assistant/rules.py), not imported across repos.
# Copied from bilingual-ticket-triage (ticket_triage/rules.py), not imported across repos.
# A few urgent patterns were added after the first evaluation run; each is marked "Added in bilingual-reply-assistant".
"""Keyword rules for the clear cases, in English and Spanish.

How a ticket is decided:
1. If any URGENT rule matches (account takeover, lost or stolen card, a charge
   the customer does not recognize), that rule decides. Safety first, even if
   the ticket mentions something else too.
2. Otherwise, if the matching rules all point to ONE category, the rule decides.
3. Otherwise (no match, or two different topics) the rules return no
   category. In this project, turn.guess_category then uses the first
   matching rule's category (or general_question if none matches).
   Only rules mark a message urgent; the AI never decides the category here.

Patterns run on lowercase text without accents ("contraseña" -> "contrasena"),
so tickets typed without accents still match.
"""

import re
from dataclasses import dataclass, field

from .language import strip_accents

URGENCY_ORDER = ["low", "normal", "high", "urgent"]


@dataclass
class Rule:
    id: str
    category: str
    patterns: list
    floor: str | None = None   # minimum urgency when this rule matches
    fraud: bool = False        # True -> takeover, lost/stolen card or unrecognized charge

    def __post_init__(self):
        self.patterns = [re.compile(p) for p in self.patterns]


@dataclass
class RuleResult:
    category: str | None = None     # None means "let the AI decide"
    rule_id: str | None = None
    matched: str = ""               # the words that triggered the rule
    floor: str | None = None
    fraud: bool = False
    candidates: list = field(default_factory=list)


RULES = [
    # --- Urgent: always go to fraud and security, always a human ----------
    Rule("takeover", "account_access", floor="urgent", fraud=True, patterns=[
        r"\b(hacked|hackearon|hackeo|hackear|jaquearon)\b",
        r"\b(someone|somebody) (changed|reset|got into|get into|logged into|logged in)",
        r"\b(password|email) (was|has been) changed\b.{0,40}\b(didn'?t|did not|never)\b",
        r"\bi (didn'?t|did not|never) change (it|my)\b",
        r"\blogins? from a (phone|device|computer)",
        r"\b(code|codigo)\b.{0,40}\b(never asked|didn'?t ask|did not ask|no pedi|no solicite)",
        r"\bcambiaron (mi|la|el) (contrasena|correo|clave|numero)",
        r"\balguien (cambio|entro|se metio)\b",
        r"\b(yo no fui|no cambie (mi|la|el))\b",
        # Scams that aim at the account: fake agents, phishing, asking for codes.
        r"\b(phishing|scam|scammed|scammer)\b",
        r"\bfake (puentara )?(agent|rep|support|call|email|website|site)\b",
        r"\b(agente|asesor|llamada|correo|pagina) fals[oa]\b",
        # A lost or stolen phone that is still logged in to the app.
        r"\b(lost|stole)( my)? (phone|cell|mobile)\b(?! ?(charger|case|cover|cable|number|bill|plan))",
        r"\b(phone|cell|mobile)( was| got)? (lost|stolen)\b",
        r"\b(perdi|perdio|robaron|extravie)( mi| el)? (celular|telefono|movil)\b",
        r"\b(celular|telefono|movil) (robado|perdido|extraviado)\b",
        # Added in bilingual-reply-assistant after the first evaluation run
        # (see NOTES.md): fake callers and handing over a code.
        r"\b(pretending|pretended|claiming|claimed) to be\b",
        r"\bdiciendo que (eran|era) (del|de) (banco|puentara)\b",
        r"\b(gave|give) (him|her|them|the caller) (the|my|a) code\b",
        r"\b(le|les) di (el|un|mi) codigo\b",
        # Added in bilingual-faq-chatbot: "hackeada",
        # someone else inside the account, and calls or messages that ask for a
        # code or password (phishing), in English and Spanish.
        r"\b(hackead[oa]s?|jaquead[oa]s?)\b",
        r"\b(someone|somebody|a stranger|a hacker)( else)? (is in|is inside|is using|got in to|has access to"
        r"|accessed|has been in|has been using|logged in to|was in)\b.{0,10}\bmy (account|app)\b",
        r"\balguien (mas )?(esta (en|dentro de|usando)|tiene acceso a|accedio a|ingreso a|entro en)\b"
        r".{0,10}\bmi (cuenta|app)\b",
        r"\b(called|call|texted|text|emailed|email|messaged|message|sms|dm|whatsapp)\b.{0,80}"
        r"\b(asked|asking|asks|ask|wanted|wants|requesting|requested)( me)?"
        r" (for|to (send|give|share|read|tell|confirm|provide))\b.{0,25}"
        r"\b(code|pin|password|otp|passcode|cvv|login)\b",
        r"\b(llamaron|llamo|llamada|escribieron|escribio|mensaje|correo|sms|whatsapp|texto)\b.{0,80}"
        r"\b(pidieron|pidio|pide|piden|pedia|pedian|solicitaron|solicito|solicita)\b.{0,25}"
        r"\b(codigo|clave|contrasena|pin|cvv)\b",
        r"\b(code|pin|password|otp|passcode)\b.{0,80}\b(is|was) (that|this|it) (really )?(you|puentara)\b",
        r"\b(codigo|clave|contrasena|pin)\b.{0,80}\b(son|fueron|eran) (ustedes|de puentara)\b",
    ]),
    Rule("card_lost_stolen", "card_lost_stolen", floor="urgent", fraud=True, patterns=[
        r"\b(lost|stolen|stole|missing)\b.{0,40}\b(card|wallet)\b",
        r"\b(card|wallet)\b.{0,40}\b(lost|stolen|missing)\b",
        r"\bcan'?t find my (debit |credit )?card\b",
        # "cloned" only next to card words ("I cloned the repo" is not fraud).
        r"\bcard\b.{0,30}\bcloned\b", r"\bcloned\b.{0,30}\bcard\b",
        r"\btarjeta\b.{0,30}\b(clonaron|clonada|clonado)\b",
        r"\b(clonaron|clonada|clonado)\b.{0,30}\btarjeta\b",
        r"\b(robaron|robo|robada|robado|perdi|perdio|perdida|extravie|extraviada)\b.{0,40}\b(tarjeta|cartera|billetera)\b",
        r"\b(tarjeta|cartera|billetera)\b.{0,40}\b(robada|robaron|perdida|extraviada)\b",
        r"\bno encuentro (mi|la) tarjeta\b",
        # Added in bilingual-reply-assistant after the first evaluation run
        # (see NOTES.md): wallets and bags taken, cards that are "gone".
        r"\bcan'?t find (my )?(wallet|purse)\b",
        r"\b(wallet|purse|bag|backpack)\b.{0,30}\b(taken|swiped|snatched|gone)\b",
        r"\bcards?\b.{0,60}\b(was|were|is) gone\b",
        r"\bse me (cayo|quedo|perdio)\b.{0,20}\btarjeta\b",
        r"\btarjeta\b.{0,40}\bya no la tengo\b",
        r"\bme (atracaron|asaltaron)\b",
    ]),
    Rule("unrecognized_charge", "charge_dispute", floor="urgent", fraud=True, patterns=[
        # "I didn't authorize it" is always fraud wording. "didn't make it" is
        # too, except "didn't make it to/in/on/back/home" (late, not fraud).
        r"\b(didn'?t|did not|never) (authori[sz]e|authori[sz]ed)\b",
        r"\b(didn'?t|did not|never) (make|made)\b(?! it (to|in|on|back|home)\b)",
        r"\b(don'?t|do not) recogni[sz]e\b",
        r"\bunauthori[sz]ed\b",
        r"\bsomeone used my card\b",
        r"\b(fraud|fraudulent|fraude|fraudulent[oa])\b",
        r"\b(estafa|estafaron|estafado|estafada)\b",
        r"\bwithout my (permission|consent)\b",
        r"\bno (lo |la )?reconozco\b",
        r"\byo no (lo |la )?(hice|autorice)\b",
        r"\bno (lo |la )?autorice\b",
        r"\b(compra|cargo|cobro|pago|retiro)s? que no (hice|autorice|reconozco)\b",
        r"\bsin mi (permiso|autorizacion)\b",
        r"\bme (sacaron|robaron) (dinero|plata)\b",
        r"\balguien uso mi tarjeta\b",
        # Added in bilingual-reply-assistant after the first evaluation run
        # (see NOTES.md): "not me", strange activity, purchases far away.
        r"\bsomeone (is using|has used|has been using) my card\b",
        r"\b(it )?wasn'?t me\b",
        r"\b(weird|strange|suspicious) (transactions|charges|payments|purchases)\b",
        r"\b(purchase|charge|transaction|payment)s?\b.{0,40}\b(another|other|a different) (city|country)\b",
        r"\byo (no|nunca) (lo |la |los |las )?(hice|autorice)\b",
        r"\bque (yo )?nunca hice\b",
        r"\b(compras|cargos|cobros|movimientos) (raros|raras|rarisimos|rarisimas|extranos|extranas"
        r"|sospechosos|sospechosas)\b",
        r"\b(compra|cargo|cobro)s? en otro (pais|ciudad)\b",
    ]),
    # --- Clear but not urgent ---------------------------------------------
    Rule("dispute", "charge_dispute", floor="high", patterns=[
        r"\bdispute\b", r"\brefund", r"\b(charged|billed)( me)? twice\b", r"\bdouble charged\b",
        r"\bcancel+ed\b.{0,40}\bcharg", r"\bcharg\w*\b.{0,40}\bcancel+ed\b", r"\bwrong amount\b",
        r"\bdisputa", r"\breembolso", r"\bdevolucion\b", r"\bdevuelvan\b",
        r"\bcobr\w* dos veces\b", r"\bdoble cobro\b", r"\bsiguen cobrando\b", r"\bcobraron de mas\b",
    ]),
    Rule("tax_forms", "tax_forms", patterns=[
        r"\b1099\b", r"\bw-?8 ?ben\b", r"\bw-?9\b", r"\btax (form|document)", r"\btaxes\b",
        r"\bimpuestos?\b", r"\bformulario fiscal",
    ]),
    Rule("identity", "identity_verification", patterns=[
        r"\bidentity\b", r"\bidentidad\b", r"\bselfie\b", r"\b(passport|pasaporte)\b",
        r"\bid verification\b", r"\bkyc\b", r"\bverification (stuck|pending|rejected|failed)",
        r"\bverificacion\b.{0,30}\b(pendiente|rechaz)",
    ]),
    Rule("access", "account_access", patterns=[
        r"\b(can'?t|cannot|unable to) (log ?in|sign in|access|get into)\b", r"\blocked out\b",
        r"\baccount (is )?locked\b", r"\bforgot (my )?password\b", r"\breset (my )?password\b",
        r"\bpassword reset\b", r"\binvalid credentials\b", r"\blogin code\b",
        r"\bno puedo (entrar|iniciar sesion|acceder|ingresar)\b", r"\bcuenta (esta )?bloqueada\b",
        r"\bolvide (mi )?contrasena\b", r"\brestablecer", r"\bno me llega el codigo\b",
        r"\bdatos son incorrectos\b",
    ]),
    Rule("transfer", "transfer_failed_pending", patterns=[
        r"\btransfer", r"\bwire\b", r"\bsent\b.{0,40}\bfail", r"\benvie\b.{0,40}\bfallo\b",
    ]),
    Rule("fees", "fees", patterns=[
        r"\bfees?\b", r"\bcomision", r"\bhow much does it cost\b", r"\bcuanto cuesta\b",
        r"\bmonthly charge\b", r"\bcargo mensual\b",
    ]),
    Rule("app_bug", "app_bug", patterns=[
        r"\bcrash", r"\bfreez", r"\bblank screen\b", r"\bdoes nothing\b", r"\bwon'?t (load|open)\b",
        r"\bbug\b", r"\bglitch", r"\bse cierra\b", r"\bse cerro\b", r"\bse congela\b",
        r"\bpantalla en blanco\b", r"\bno hace nada\b", r"\bno carga\b", r"\bse traba\b",
    ]),
]


def higher_urgency(a, b):
    """Return the more urgent of two levels. None counts as no floor."""
    if a is None:
        return b
    if b is None:
        return a
    return a if URGENCY_ORDER.index(a) >= URGENCY_ORDER.index(b) else b


def fold(text):
    """Lowercase, no accents, straight apostrophes, ONE character out for each
    character in. Keeping the length lets us quote the customer's original
    words ("código", "pedí") from the position of a match."""
    out = []
    for ch in text:
        folded = strip_accents(ch).replace("’", "'")
        out.append(folded if len(folded) == 1 else ch.lower()[:1] or ch)
    return "".join(out)


def apply_rules(text):
    """Run every rule on the (already masked) ticket text."""
    normalized = fold(text)
    hits = []
    for rule in RULES:
        for pattern in rule.patterns:
            match = pattern.search(normalized)
            if match:
                hits.append((rule, text[match.start():match.end()]))
                break
    if not hits:
        return RuleResult()

    urgent = [(r, m) for r, m in hits if r.floor == "urgent"]
    if urgent:
        rule, matched = urgent[0]
        return RuleResult(rule.category, rule.id, matched, "urgent", rule.fraud,
                          [rule.category])

    floor = None
    for rule, _ in hits:
        floor = higher_urgency(floor, rule.floor)
    candidates = list(dict.fromkeys(rule.category for rule, _ in hits))
    if len(candidates) == 1:
        rule, matched = hits[0]
        return RuleResult(rule.category, rule.id, matched, floor, rule.fraud, candidates)
    # Two different topics: the AI picks the main one, the floor still applies.
    return RuleResult(None, None, "", floor, False, candidates)
