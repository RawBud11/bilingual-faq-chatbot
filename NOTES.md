# Design notes and known limits

## Web server
- No web framework. `app.py` uses the Python standard library: `ThreadingHTTPServer` and
  one `BaseHTTPRequestHandler`.

## Design decisions
- **Two small extra routes** besides the four main ones: `GET /kb/<id>` (the "Source" link
  under an answer needs a page to open) and `GET /api/status` (lets the widget show the demo
  badge before the first message). Both are read-only.
- **Offer vs. handoff.** A handoff record is written only when a person really takes over:
  urgent case, the customer asks (words or button), or two "no answer" turns in a row.
  Disputes, account access, identity verification, account-specific questions, typed secrets,
  blocked answers and "no answer" get an *offer* (a "Talk to a person" button in the reply).
  A button handoff after an account-specific refusal is marked high priority.
- **Order of checks.** Mask, language, urgent, "asks for a person", other language,
  sensitive warning, account-specific. "Asks for a person" comes before the sensitive
  warning and account-specific checks because a request for a person must *always* create
  a handoff. Urgent stays first. If a secret was typed, the warning is put in
  front of the urgent or handoff reply.
- **Sensitive warning** fires for card numbers, CVVs, PINs and codes. Emails and phone numbers
  are masked too, but do not trigger the warning (they are personal data, not secrets).
  When the warning fires and the case is not urgent, the bot stops there and offers a person.
- **"Other" language.** Very short messages with no English or Spanish words ("ok", "1099?")
  get the widget's UI language instead of the bilingual "English or Spanish only" message
  (`OTHER_LANGUAGE_MIN_WORDS = 3` in `config.py`).
- **Handoff category** comes from the rules only, else `general_question`. Search is not used
  for it: "What's my balance?" shares "balance" with the transfer article.
- **Live mode sends only the current message** (masked, tags stripped) plus the retrieved
  articles, not the earlier turns. Less text for an injection to hide in.
- **`--record`** is on `demo.py` only (it records the scripted conversations), not on `app.py`.
- **`--handoffs PATH`** on `demo.py` and `app.py`, so tests never overwrite
  `output/handoffs.jsonl`. `demo.py` starts that file fresh on each run (ids start at H-0001).
- Inline `[KB-..]` citations are removed from the answer text; the widget shows the source as
  a link under the answer instead.
- The widget's `?open` query (`http://127.0.0.1:8000/?open`) opens the chat on load. It was
  used for testing; the screenshots were taken with a temporary driver page that was deleted.
- `ChatServer.allow_reuse_address` is off on Windows: there, address reuse lets a second
  server bind a busy port silently, so "port busy" would never be reported.

## Copied from bilingual-reply-assistant (not imported)
`mask.py`, `language.py`, `rules.py`, `retrieve.py`, `guardrails.py`, `kb.py`, the
client/fixture pattern in `ai.py`, the `strings.py` pattern, `kb/` (8 EN/ES placeholder
articles), and tests `test_mask.py`, `test_language.py`, `test_rules.py`,
`test_guardrails.py` (checker part only), `test_retrieve.py`. Each file says so at the top.

## Evaluation record (synthetic data)
- `data/chat_labeled.csv` (76 messages, 46 paraphrases) was written before
  `account_specific.py` and before opening the copied `rules.py`. Honest caveat: the labels
  and the account-specific and "asks for a person" patterns were written in the same
  AI-assisted build session, with the labels in mind. So the first run is not fully
  blind for those two parts.
- First run, saved in `docs/eval_first_run.txt`: overall 70/76 (92%), paraphrases 42/46,
  false handoffs/refusals on answerable questions 1/37, answered-when-should-refuse 0/11,
  urgent answered 0/10.
- One round of changes after the first run, then stopped:
  - `account_specific.py`: "verify" / "verificar" removed from the lookup verbs
    ("verificar mi cuenta" means identity verification).
  - `retrieve.py`: Spanish "puedo puedes puede pueden tienen tienes" added as stopwords
    ("can" and "have" already were); synonyms "pedido" and "order" (item not received).
- After the round: 73/76 (96%), paraphrases 45/46, false handoffs 0/37. Optimistic: the changes
  came from misses in the same file.
- `data/chat_fresh.csv`: 17 messages written in a separate review step after tuning, never
  used for tuning. `evaluate.py` reports it on its own line. During the build, "I want a
  human" was noticed as NOT detected as a request for a person and deliberately not tuned.
  The review step found it and similar misses; they were fixed with general patterns (see below).

## Fixes after review (general patterns, not tuned to data/chat_fresh.csv)
- Requests for a person (`handoff.py`): "want / need / I'd like / can I get" and "quiero /
  necesito / quisiera" followed closely by a people word, and messages that are only a people
  word with optional "please" / "por favor" ("agent", "human please", "Agente, por favor").
  The people word must follow the verb closely, so "Quiero pagarle a alguien" and "I need
  someone's account number" are not requests.
- Takeover and phishing (`rules.py`, takeover rule, marked "Added in bilingual-faq-chatbot"):
  "hackeada/hackeado", someone else in or using the account (EN/ES), a call, text, email or
  message that asks for a code, PIN or password (EN/ES), and "is that you? / ¿son ustedes?"
  near a code or password. All urgent: immediate handoff, AI not called. Checked against
  login-help messages ("How do I reset my password?", "No me llega el código").
- Passwords (`mask.py`): the word after "password is / password: / pw: / contraseña es /
  contraseña: / mi clave es / clave:" becomes `[PASSWORD MASKED]` and counts as a secret, so
  the sensitive warning fires and it never reaches the AI, the inbox or handoffs.jsonl.
  "mi clave es 4821" is now masked as a password instead of a code.
- `data/chat_labeled.csv` was not changed; the fresh-set rows were not added to it.

## Known limits
- Keyword search only matches words. Remaining misses after tuning: "¿Cómo veo mi saldo en la
  app?" gets the transfer article ("saldo"), "¿Tienen tarjetas de crédito?" and "Do you have a
  business plan for teams of five people?" get the lost-card article ("tarjeta", "team").
  The customer sees a wrong but harmless short answer, with its source shown.
- Account-specific, "asks for a person" and phishing detection are phrase patterns; new
  wording slips through. Phishing patterns need a contact word (call, text, email, mensaje...)
  near a request for a code or password; "someone wants my code" with no contact word is missed.
- Checker limits carried from bilingual-reply-assistant: negation is per comma-separated part
  ("No olvides enviarnos tu PIN" would pass); the citation check confirms an article was
  retrieved, not that the answer says what the article says.
- Mask tokens stay in English in Spanish chats. Names, account numbers and addresses are not
  masked. Passwords are masked only after a label ("my password is ...", "contraseña: ...").
  A password typed with no label ("Sunflower2024! log me in"), or after a word in the
  exclusion list ("my password is the ..."), is NOT masked. A password that starts with one
  of those common words ("my password is newyork1") would not be masked either.
- The widget history comes from the browser and is not trusted: it is cut to 20 turns of
  2,000 characters and masked again on the server, but a customer could still edit what it
  says the bot answered (it only affects the two-miss rule and the stored transcript).
- Local demo, not production-hardened: no login, no rate limiting, no HTTPS, handoffs in a
  JSONL file. Ctrl+C stops the server; the "Server stopped." line was not checked on Windows
  in an automated test.
- Fixtures are keyed by the normalized message. If a demo conversation changes, edit the
  fixtures or re-record with `python demo.py --live --record`.

## Ideas for later (only if a client asks)
- A "yes" reply to a handoff offer could create the handoff (now the customer taps the button
  or types "talk to a person").
- Send the last few turns to the AI in live mode, if follow-up questions matter.
- Connect a real helpdesk (Zendesk, Freshdesk, Intercom) instead of the JSONL file.
- Light stemming instead of synonyms; a minimum of two matching words for one-word hits.
