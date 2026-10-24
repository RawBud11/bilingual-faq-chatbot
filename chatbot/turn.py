"""One chat turn: from the customer's message to the bot's reply, in this order:

mask -> language -> urgent -> asks for a person -> other language -> sensitive data
-> account-specific -> search articles -> answer -> guardrails -> two-miss rule

Actions (what happened this turn):
  answer              answered from one help article, with its source
  no_answer           no article, or no usable AI answer: says so, offers a person
  refuse_account      needs someone who can see the account: refuses, offers a person
  sensitive_warning   the customer typed a card number, CVV, PIN or code: warns, offers a person
  blocked             an answer failed the guardrails: never shown, safe reply instead
  other_language      not English or Spanish: short bilingual message, offers a person
  handoff_urgent      lost or stolen card, fraud, takeover: handoff now, AI not called
  handoff_requested   the customer asked for a person (typed it, or tapped the button)
  handoff_two_misses  two "no answer" turns in a row
Urgent and "asks for a person" come before everything else on purpose: those
customers must reach a person even if they also typed a card number.
The server keeps no state: the widget sends the conversation so far each time.
"""

import re

import config

from .account_specific import account_specific_match
from .ai import CITATION_RE, AIError, build_request, parse_answer
from .guardrails import check_draft
from .handoff import build_record, clean_history, higher_urgency, wants_human
from .language import detect_language
from .mask import CARD_MASK, CODE_MASK, PASSWORD_MASK, mask_sensitive
from .rules import apply_rules
from .strings import t

MISS_ACTIONS = {"no_answer"}


def reply_language(language, ui_lang, word_count):
    """Reply in the customer's language. Mixed EN/ES gets Spanish. A very
    short message with no EN/ES words ("ok", "1099?") gets the widget's UI
    language. Returns None for a real other language."""
    if language in ("en", "es"):
        return language
    if language == "mixed":
        return config.MIXED_REPLY_LANGUAGE
    return ui_lang if word_count < config.OTHER_LANGUAGE_MIN_WORDS else None


def typed_secrets(original, masked):
    """True when masking hid a card number, CVV, PIN, code or password (not
    just an email or phone: those are hidden too, but are not secrets)."""
    return any(masked.count(token) > original.count(token)
               for token in (CARD_MASK, CODE_MASK, PASSWORD_MASK))


def is_urgent(rule):
    """Copied from bilingual-reply-assistant (holding.is_urgent)."""
    return rule.floor == "urgent" or rule.category == "card_lost_stolen"


def guess_category(text):
    """Category for a handoff or a refusal: the rules, else general_question.
    Search is not used here on purpose: "What's my balance?" shares the word
    "balance" with the transfer article, but it is not a transfer question."""
    rule = apply_rules(text)
    return rule.category or (rule.candidates[0] if rule.candidates else "general_question")


def clean_citations(reply):
    """The widget shows the source under the answer, so the inline [KB-..]
    markers are removed from the text the customer reads."""
    reply = CITATION_RE.sub("", reply)
    reply = re.sub(r"[ \t]+([.,;:!?])", r"\1", reply)
    return re.sub(r"[ \t]{2,}", " ", reply).strip()


def join(*parts):
    return "\n\n".join(p for p in parts if p)


def new_result(language, reply_lang, masked="", masked_count=0):
    return {"masked_message": masked, "masked_count": masked_count, "language": language,
            "reply_lang": reply_lang, "action": "", "reply": "", "category": "", "source": None,
            "answer_from": "fixed", "offer_handoff": False, "handoff": None, "blocked": None,
            "ai_problem": None}


def save_handoff(store, result, transcript, *, action, trigger, category, urgency, make_reply):
    """Write one handoff record. make_reply(ref) builds the customer's reply,
    which quotes the reference number and is saved in the transcript too."""
    def make_record(ref):
        reply = make_reply(ref)
        result.update(action=action, reply=reply, category=category,
                      handoff={"id": ref, "urgency": urgency, "category": category})
        return build_record(language=result["language"], reply_lang=result["reply_lang"],
                            category=category, urgency=urgency, trigger=trigger,
                            transcript=transcript + [{"role": "bot", "text": reply, "action": action}])
    store.add(make_record)
    return result


def request_handoff(store, result, transcript, trigger, warning=""):
    """The customer asked for a person (typed it, or tapped the button)."""
    lang = result["reply_lang"]
    customer_text = " ".join(e["text"] for e in transcript if e["role"] == "customer")
    category = guess_category(customer_text)
    urgency = config.CATEGORY_URGENCY[category]
    # A question the bot refused because it needs the account is high priority.
    if any(e.get("action") == "refuse_account" for e in transcript):
        urgency = higher_urgency(urgency, "high")
    return save_handoff(store, result, transcript, action="handoff_requested", trigger=trigger,
                        category=category, urgency=urgency,
                        make_reply=lambda ref: join(warning, t(lang, "handoff_created").format(ref=ref),
                                                    t(lang, "honest_note")))


def run_turn(message, history, *, client, indexes, store, ui_lang="en",
             model=config.DEFAULT_MODEL, threshold=config.CONFIDENCE_THRESHOLD):
    """Answer one customer message. Returns a dict; app.public_view picks the
    part the browser gets (a blocked answer never leaves the server)."""
    ui_lang = ui_lang if ui_lang in ("en", "es") else "en"
    masked, masked_count = mask_sensitive(message)
    language = detect_language(masked)
    lang = reply_language(language, ui_lang, len(masked.split()))
    shown = lang or ui_lang
    result = new_result(language, shown, masked, masked_count)
    secrets = typed_secrets(message or "", masked)
    warning = t(shown, "sensitive_warning") if secrets else ""
    history = clean_history(history)
    transcript = history + [{"role": "customer", "text": masked}]

    def finish(action, reply, offer=False):
        result.update(action=action, reply=join(reply, t(shown, "offer")) if offer else reply,
                      offer_handoff=offer)
        return result

    # 1. Urgent: a person handles it now. The AI is never called.
    rule = apply_rules(masked)
    if is_urgent(rule):
        return save_handoff(
            store, result, transcript, action="handoff_urgent", trigger="urgent",
            category=rule.category or "card_lost_stolen", urgency="urgent",
            make_reply=lambda ref: join(warning, t(shown, "urgent_holding").format(ref=ref),
                                        t(shown, "honest_note"), t(shown, "never_ask")))

    # 2. The customer asks for a person: always a handoff.
    if wants_human(masked):
        return request_handoff(store, result, transcript, "requested", warning)

    # 3. Not English or Spanish.
    if lang is None:
        return finish("other_language", t("en", "other_language"))

    # 4. Card numbers, CVVs, PINs or codes typed in the chat: warn, do not go on.
    if secrets:
        return finish("sensitive_warning", join(warning, t(lang, "never_ask")), offer=True)

    # 5. Questions about this customer's account: refuse. The AI is not called.
    if account_specific_match(masked):
        result["category"] = guess_category(masked)
        return finish("refuse_account", t(lang, "refuse_account"), offer=True)

    # 6. Search the help articles in the reply language, then answer.
    articles = [a for a, _ in indexes[lang].search(masked)]
    source = None
    if articles:
        request = build_request(masked, articles, lang, model)
        try:
            answer = parse_answer(client.complete(request), [a.id for a in articles], threshold)
            source = next(a for a in articles if a.id == answer["cited"][0])
            reply, answer_from = clean_citations(answer["reply"]), client.source_for(request)
        except AIError as error:
            if error.code == "no_fixture":  # demo mode, no sample answer: use the article
                source, reply, answer_from = articles[0], articles[0].short_answer, "template"
            else:                           # never guess: treat it as "no answer"
                result["ai_problem"] = error.code
                result["ai_fatal"] = error.fatal

    if source is not None:
        if source.category == "tax_forms":
            reply = join(reply, t(lang, "tax_disclaimer"))
        result.update(category=rule.category or source.category, answer_from=answer_from,
                      source={"id": source.id, "title": source.title})
        # 7. Guardrails: a blocked answer is never shown to the customer.
        findings = check_draft(reply)
        if findings:
            result.update(blocked=findings[0], source=None, answer_from="fixed")
            return finish("blocked", join(t(lang, "blocked_fallback"), t(lang, "never_ask")),
                          offer=True)
        return finish("answer", reply, offer=source.category in config.OFFER_HANDOFF_CATEGORIES)

    # 8. No answer. Two in a row: a person takes over.
    last_bot = next((e for e in reversed(history) if e["role"] == "bot"), None)
    if last_bot and last_bot.get("action") in MISS_ACTIONS:
        category = guess_category(" ".join(e["text"] for e in transcript if e["role"] == "customer"))
        return save_handoff(
            store, result, transcript, action="handoff_two_misses", trigger="two_misses",
            category=category, urgency=config.CATEGORY_URGENCY[category],
            make_reply=lambda ref: join(t(lang, "handoff_two_misses").format(ref=ref),
                                        t(lang, "honest_note")))
    return finish("no_answer", t(lang, "no_answer"), offer=True)


def run_button_handoff(history, *, store, ui_lang="en"):
    """The customer tapped "Talk to a person". Always creates a handoff.

    The reply follows the language of the customer's last message, or the
    widget's UI language when there is none.
    """
    ui_lang = ui_lang if ui_lang in ("en", "es") else "en"
    transcript = clean_history(history)
    customer = [e["text"] for e in transcript if e["role"] == "customer"]
    language = detect_language(customer[-1]) if customer else ui_lang
    lang = reply_language(language, ui_lang, len(customer[-1].split()) if customer else 0) or ui_lang
    return request_handoff(store, new_result(language, lang), transcript, "button")
