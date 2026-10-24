"""Every text a person reads, in English and Spanish. One table per language.

Pattern copied from bilingual-reply-assistant (reply_assistant/strings.py).
Two kinds of text live here:
- Customer-facing chat messages, picked by the customer's language.
- UI text for the terminal (app.py, demo.py, evaluate.py, picked with
  --ui-lang) and the agent inbox (picked with ?lang=es).
The widget's own buttons and labels are in static/widget.js (one object per
language), because the browser needs them before it talks to the server.

Spanish uses "tú", neutral Latin American Spanish. "Freeze your card in the
Puentara app" is specific to the fictional Puentara: adapt it for a real client.
"""

PERSON_BUTTON = {"en": "Talk to a person", "es": "Hablar con una persona"}

STRINGS = {
    "en": {
        # --- Chat messages for the customer --------------------------------
        "never_ask": "We never ask for your PIN, CVV, password or one-time codes.",
        "offer": f'Want a person on our team to help? Tap "{PERSON_BUTTON["en"]}".',
        "honest_note": "A person on our team will review this; this demo does not connect to a real helpdesk.",
        "urgent_holding": (
            "Thanks for telling us right away. Your security comes first. If your card may be lost "
            "or someone else may be using your account, freeze your card now in the Puentara app "
            "(Cards > Freeze card). I've passed this to a person on our team as urgent. "
            "Your reference is {ref}."
        ),
        "handoff_created": "Thanks. I've passed your conversation to a person on our team. Your reference is {ref}.",
        "handoff_two_misses": (
            "I couldn't find an answer twice in a row, so I've passed your conversation to a person "
            "on our team. Your reference is {ref}."
        ),
        "sensitive_warning": (
            "For your safety, please don't share card numbers, CVVs, PINs, passwords or codes in "
            "this chat. I've hidden what you typed."
        ),
        "refuse_account": "I can't see or change anything in your account from this chat, so I can't answer that one.",
        "no_answer": "I don't have an answer for that in our help center, and I'd rather not guess.",
        "blocked_fallback": "Sorry, I can't give you a safe answer to that here.",
        "other_language": (
            "Sorry, I can only help in English or Spanish. / Lo siento, solo puedo ayudarte en "
            "inglés o español.\n\n"
            f'A person on our team can help: tap "{PERSON_BUTTON["en"]}". / Una persona de nuestro '
            f'equipo puede ayudarte: toca "{PERSON_BUTTON["es"]}".'
        ),
        "tax_disclaimer": (
            "This is general information, not tax advice. For questions about your own taxes, "
            "check the official tax authority (the IRS in the US, or the tax agency in your "
            "country) or talk to a tax professional."
        ),
        # --- Errors returned by the API (shown in the widget) ---------------
        "error_too_long": "Your message is too long. Please keep it under 1,000 characters.",
        "error_empty": "Please type a question first.",
        "error_bad_request": "Something went wrong with that message. Please reload the page and try again.",
        "error_too_big": "That request is too large. Please reload the page and try again.",
        "error_server": "Sorry, something went wrong on our side. Please try again in a moment.",
        # --- Handoff record and agent inbox --------------------------------
        "summary": '{urgency} | {category} | language: {language} | trigger: {trigger}. Last customer message: "{last}"',
        "urgency": {"urgent": "Urgent", "high": "High", "normal": "Normal", "low": "Low"},
        "languages": {"en": "English", "es": "Spanish", "mixed": "mixed EN/ES", "other": "other"},
        "triggers": {
            "urgent": "urgent case (lost or stolen card, fraud or possible takeover), AI not called",
            "requested": "customer asked for a person",
            "button": f'customer tapped "{PERSON_BUTTON["en"]}"',
            "two_misses": "two questions in a row without an answer",
        },
        "categories": {
            "account_access": "Account access",
            "identity_verification": "Identity verification",
            "card_lost_stolen": "Card lost or stolen",
            "transfer_failed_pending": "Failed or pending transfer",
            "charge_dispute": "Charge dispute",
            "fees": "Fees",
            "tax_forms": "Tax forms",
            "app_bug": "App bug",
            "general_question": "General question",
        },
        "inbox": {
            "title": "Agent inbox: handoffs from the chat",
            "banner": "Puentara is a fictional company. Read-only demo inbox: nothing here is sent to customers, and it does not connect to a real helpdesk.",
            "count": "{count} handoffs, urgent first. Source: {path}",
            "empty": "No handoffs yet. Open the chat and tap \"Talk to a person\", or run: python demo.py",
            "switch": "Ver en español",
            "reference": "Reference", "time": "Time (UTC)", "urgency": "Urgency",
            "category": "Category", "language": "Language", "trigger": "Trigger",
            "summary": "Summary", "transcript": "Transcript (masked)",
            "customer": "Customer", "bot": "Bot",
        },
        "article": {"label": "Help article (placeholder content, fictional company Puentara)",
                    "back": "Back to the help center", "missing": "Article not found."},
        # --- Terminal ------------------------------------------------------
        "demo_no_key": "Demo mode: no API key found, using sample answers from fixtures/ (hand-written examples, not real model output). Other questions get a template answer (no AI).",
        "demo_with_key": "Demo mode: using sample answers from fixtures/ (hand-written examples, not real model output). Add --live to call Claude with your key.",
        "live_mode": "Live mode: calling Claude ({model}) for questions the help center can answer.",
        "need_key": "--live needs an API key. Add ANTHROPIC_API_KEY to .env, or run without --live for demo mode.",
        "record_needs_live": "--record only works with --live (it saves real API answers to fixtures/).",
        "recorded": "Saved {count} recorded AI answers to {path}.",
        "fatal_ai": "Stopped: {error}",
        "server_open": "Open http://{host}:{port} for the chat widget, and http://{host}:{port}/agent for the agent inbox. Press Ctrl+C to stop.",
        "port_busy": "Port {port} is busy. Try another one, for example: python app.py --port {next_port}",
        "stopped": "Server stopped.",
        "sources": {
            "fixed": "fixed message (no AI)",
            "template": "template answer (no AI), from the article's short answer",
            "hand-written": "hand-written example, not real model output",
            "recorded": "recorded from a real API call",
            "live": "Claude ({model})",
        },
        "ai_problems": {
            "timeout": "the API took too long", "connection": "could not reach the API",
            "rate_limit": "API rate limit reached", "server": "API server error",
            "bad_request": "the API rejected the request", "bad_json": "the answer is not valid JSON",
            "no_reply": "the answer has no text", "bad_confidence": "confidence is not a number from 0 to 1",
            "low_confidence": "the AI was not sure", "no_citation": "the answer cites no help article",
            "bad_citation": "the answer cites an article that was not retrieved",
            "auth": "the API key was rejected. Check ANTHROPIC_API_KEY in .env.",
            "permission": "this API key cannot use that model. Check your Anthropic account.",
            "model": "model not found. Check ANTHROPIC_MODEL in .env.",
        },
        "demo": {
            "fresh_file": "Starting a fresh {path} for this demo.",
            "title": "=== {n}. {title} ===",
            "customer": "Customer", "bot": "Bot", "button": f'[taps "{PERSON_BUTTON["en"]}"]',
            "details": "  -> action: {action} | language: {language} -> reply in {reply_lang}",
            "source": "  -> source: {source} ({title}) | answer from: {answer_from}",
            "masked": "  -> masked before anything else ({count}): {text}",
            "blocked": "  -> the checker blocked an answer ({reason}); the customer never saw it",
            "handoff": "  -> Handoff {ref} ({urgency}, {category})",
            "footer": "{count} handoffs written to {path}. Nothing was sent.",
            "next": "Next: python app.py, then open http://127.0.0.1:8000/agent to see them in the inbox.",
        },
        "eval": {
            "header": "Synthetic sample data. Not real-world accuracy.",
            "about": "AI not called: every answer is a template from the top article, so this measures masking, language, rules, account-specific checks and keyword search.",
            "tuned_note": "Note: one round of changes was made after a first run on this same file, and the messages and the patterns were written in the same build session, so these numbers are optimistic. The fresh set is the honest check. First-run output: docs/eval_first_run.txt.",
            "file": "{path}: {count} messages",
            "first_run_note": "first run {value}",
            "recall_title": "Recall per expected action",
            "recall_line": "  {action:<20} {hits}/{total} ({pct})",
            "overall": "Overall correct action",
            "false_handoffs": "False handoffs or refusals on answerable questions",
            "wrong_answers": "Answered when it should have refused",
            "urgent_answered": "Urgent messages answered by the bot",
            "fresh": "Fresh set (data/chat_fresh.csv, written after tuning, never tuned on)",
            "fresh_empty": "Fresh set (data/chat_fresh.csv): empty, no messages yet.",
            "misses": "Every miss (id, expected -> got, message)",
            "no_misses": "  none",
            "saved": "Saved this run to {path}.",
        },
    },
    "es": {
        # --- Mensajes del chat para el cliente -----------------------------
        "never_ask": "Nunca te pediremos tu PIN, CVV, contraseña ni códigos de un solo uso.",
        "offer": f'¿Quieres que te ayude una persona de nuestro equipo? Toca "{PERSON_BUTTON["es"]}".',
        "honest_note": "Una persona de nuestro equipo revisará esto; esta demo no está conectada a un sistema de soporte real.",
        "urgent_holding": (
            "Gracias por avisarnos de inmediato. Tu seguridad es lo primero. Si tu tarjeta se perdió "
            "o crees que alguien más está usando tu cuenta, congela tu tarjeta ya mismo en la app de "
            "Puentara (Tarjetas > Congelar tarjeta). Ya le pasé tu caso como urgente a una persona "
            "de nuestro equipo. Tu número de referencia es {ref}."
        ),
        "handoff_created": "Gracias. Ya le pasé tu conversación a una persona de nuestro equipo. Tu número de referencia es {ref}.",
        "handoff_two_misses": (
            "No encontré una respuesta dos veces seguidas, así que le pasé tu conversación a una "
            "persona de nuestro equipo. Tu número de referencia es {ref}."
        ),
        "sensitive_warning": (
            "Por tu seguridad, no compartas números de tarjeta, CVV, PIN, contraseñas ni códigos "
            "en este chat. Ya oculté lo que escribiste."
        ),
        "refuse_account": "Desde este chat no puedo ver ni cambiar nada de tu cuenta, así que no puedo responder eso.",
        "no_answer": "No tengo una respuesta para eso en nuestro centro de ayuda y prefiero no adivinar.",
        "blocked_fallback": "Lo siento, aquí no puedo darte una respuesta segura para eso.",
        "other_language": None,  # filled in below: the same bilingual text as English
        "tax_disclaimer": (
            "Esta es información general, no asesoría fiscal. Para preguntas sobre tus propios "
            "impuestos, consulta la autoridad tributaria oficial (el IRS en EE. UU. o la entidad "
            "de impuestos de tu país) o habla con un profesional en impuestos."
        ),
        # --- Errores de la API (se muestran en el widget) -------------------
        "error_too_long": "Tu mensaje es muy largo. Escríbelo en menos de 1000 caracteres.",
        "error_empty": "Primero escribe tu pregunta.",
        "error_bad_request": "Algo salió mal con ese mensaje. Vuelve a cargar la página e inténtalo de nuevo.",
        "error_too_big": "La solicitud es demasiado grande. Vuelve a cargar la página e inténtalo de nuevo.",
        "error_server": "Lo siento, algo salió mal de nuestro lado. Inténtalo de nuevo en un momento.",
        # --- Registro de traspaso y bandeja de agentes ---------------------
        "summary": '{urgency} | {category} | idioma: {language} | motivo: {trigger}. Último mensaje del cliente: "{last}"',
        "urgency": {"urgent": "Urgente", "high": "Alta", "normal": "Normal", "low": "Baja"},
        "languages": {"en": "inglés", "es": "español", "mixed": "mezcla inglés/español", "other": "otro"},
        "triggers": {
            "urgent": "caso urgente (tarjeta perdida o robada, fraude o posible robo de cuenta), no se llamó a la IA",
            "requested": "el cliente pidió hablar con una persona",
            "button": f'el cliente tocó "{PERSON_BUTTON["es"]}"',
            "two_misses": "dos preguntas seguidas sin respuesta",
        },
        "categories": {
            "account_access": "Acceso a la cuenta",
            "identity_verification": "Verificación de identidad",
            "card_lost_stolen": "Tarjeta perdida o robada",
            "transfer_failed_pending": "Transferencia fallida o pendiente",
            "charge_dispute": "Disputa de cargo",
            "fees": "Comisiones",
            "tax_forms": "Formularios de impuestos",
            "app_bug": "Error en la app",
            "general_question": "Pregunta general",
        },
        "inbox": {
            "title": "Bandeja de agentes: traspasos desde el chat",
            "banner": "Puentara es una empresa ficticia. Bandeja de demostración de solo lectura: nada de lo que ves aquí se envía a los clientes y no está conectada a un sistema de soporte real.",
            "count": "{count} traspasos, primero los urgentes. Archivo: {path}",
            "empty": "Todavía no hay traspasos. Abre el chat y toca \"Hablar con una persona\", o ejecuta: python demo.py",
            "switch": "View in English",
            "reference": "Referencia", "time": "Hora (UTC)", "urgency": "Urgencia",
            "category": "Categoría", "language": "Idioma", "trigger": "Motivo",
            "summary": "Resumen", "transcript": "Conversación (datos ocultos)",
            "customer": "Cliente", "bot": "Bot",
        },
        "article": {"label": "Artículo de ayuda (contenido de ejemplo, empresa ficticia Puentara)",
                    "back": "Volver al centro de ayuda", "missing": "No se encontró el artículo."},
        # --- Terminal ------------------------------------------------------
        "demo_no_key": "Modo demo: no se encontró una clave de API, se usan respuestas de ejemplo de fixtures/ (escritas a mano, no son respuestas reales del modelo). Las demás preguntas reciben una respuesta de plantilla (sin IA).",
        "demo_with_key": "Modo demo: se usan respuestas de ejemplo de fixtures/ (escritas a mano, no son respuestas reales del modelo). Agrega --live para llamar a Claude con tu clave de API.",
        "live_mode": "Modo en vivo: se llama a Claude ({model}) para las preguntas que el centro de ayuda puede responder.",
        "need_key": "--live necesita una clave de API. Agrega ANTHROPIC_API_KEY a tu archivo .env, o ejecútalo sin --live para usar el modo demo.",
        "record_needs_live": "--record solo funciona con --live (guarda respuestas reales de la API en fixtures/).",
        "recorded": "Se guardaron {count} respuestas grabadas de la IA en {path}.",
        "fatal_ai": "Se detuvo: {error}",
        "server_open": "Abre http://{host}:{port} para ver el widget del chat, y http://{host}:{port}/agent para la bandeja de agentes. Presiona Ctrl+C para detenerlo.",
        "port_busy": "El puerto {port} está ocupado. Prueba con otro, por ejemplo: python app.py --port {next_port}",
        "stopped": "Servidor detenido.",
        "sources": {
            "fixed": "mensaje fijo (sin IA)",
            "template": "respuesta de plantilla (sin IA), hecha con la respuesta corta del artículo",
            "hand-written": "ejemplo escrito a mano, no es una respuesta real del modelo",
            "recorded": "grabado de una llamada real a la API",
            "live": "Claude ({model})",
        },
        "ai_problems": {
            "timeout": "la API tardó demasiado", "connection": "no se pudo conectar con la API",
            "rate_limit": "se alcanzó el límite de uso de la API", "server": "error en el servidor de la API",
            "bad_request": "la API rechazó la solicitud", "bad_json": "la respuesta no es JSON válido",
            "no_reply": "la respuesta no trae texto", "bad_confidence": "la confianza no es un número de 0 a 1",
            "low_confidence": "la IA no estaba segura", "no_citation": "la respuesta no cita ningún artículo",
            "bad_citation": "la respuesta cita un artículo que no salió en la búsqueda",
            "auth": "la API rechazó la clave. Revisa ANTHROPIC_API_KEY en tu archivo .env.",
            "permission": "esta clave de API no puede usar ese modelo. Revisa tu cuenta de Anthropic.",
            "model": "no se encontró el modelo. Revisa ANTHROPIC_MODEL en tu archivo .env.",
        },
        "demo": {
            "fresh_file": "Se empieza un archivo {path} nuevo para esta demo.",
            "title": "=== {n}. {title} ===",
            "customer": "Cliente", "bot": "Bot", "button": f'[toca "{PERSON_BUTTON["es"]}"]',
            "details": "  -> acción: {action} | idioma: {language} -> respuesta en {reply_lang}",
            "source": "  -> fuente: {source} ({title}) | respuesta de: {answer_from}",
            "masked": "  -> datos ocultos antes de todo lo demás ({count}): {text}",
            "blocked": "  -> la revisión bloqueó una respuesta ({reason}); el cliente nunca la vio",
            "handoff": "  -> Traspaso {ref} ({urgency}, {category})",
            "footer": "Se escribieron {count} traspasos en {path}. No se envió nada.",
            "next": "Siguiente paso: python app.py, y luego abre http://127.0.0.1:8000/agent para verlos en la bandeja.",
        },
        "eval": {
            "header": "Datos de ejemplo sintéticos. No miden la precisión en el mundo real.",
            "about": "No se llama a la IA: cada respuesta es una plantilla del primer artículo, así que esto mide el ocultamiento de datos, el idioma, las reglas, la detección de preguntas sobre la cuenta y la búsqueda por palabras clave.",
            "tuned_note": "Nota: se hizo una ronda de cambios después de una primera ejecución con este mismo archivo, y los mensajes y los patrones se escribieron en la misma sesión de desarrollo, así que estos números son optimistas. El grupo nuevo es la prueba honesta. Resultado de la primera ejecución: docs/eval_first_run.txt.",
            "file": "{path}: {count} mensajes",
            "first_run_note": "primera ejecución {value}",
            "recall_title": "Aciertos por acción esperada",
            "recall_line": "  {action:<20} {hits}/{total} ({pct})",
            "overall": "Acción correcta en total",
            "false_handoffs": "Traspasos o rechazos por error en preguntas que se podían responder",
            "wrong_answers": "Respondidas cuando debía rechazarlas",
            "urgent_answered": "Mensajes urgentes respondidos por el bot",
            "fresh": "Grupo nuevo (data/chat_fresh.csv, escrito después del ajuste, nunca usado para ajustar)",
            "fresh_empty": "Grupo nuevo (data/chat_fresh.csv): vacío, todavía no tiene mensajes.",
            "misses": "Todos los fallos (id, esperado -> obtenido, mensaje)",
            "no_misses": "  ninguno",
            "saved": "Esta ejecución se guardó en {path}.",
        },
    },
}
STRINGS["es"]["other_language"] = STRINGS["en"]["other_language"]


def t(lang, key):
    """Look up a string, e.g. t("es", "no_answer")."""
    return STRINGS[lang][key]
