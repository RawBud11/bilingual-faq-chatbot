// Puentara help chat widget. Puentara is a fictional company (demo only).
// Plain JavaScript, no build step. Embed it on any page with one line:
//   <script src="http://127.0.0.1:8000/widget.js" defer></script>
// It talks to the server it was loaded from (see app.py). Bot text is always
// inserted with textContent, never innerHTML, so typed HTML is shown as text.
(function () {
  "use strict";

  // All widget labels, one object per language.
  var STRINGS = {
    en: {
      launcher: "Help chat",
      title: "Puentara help chat",
      fictional: "Puentara is a fictional company. Demo only.",
      demo: "demo mode: sample answers",
      greeting: "Hi! I answer questions from the Puentara help center, in English or Spanish. " +
        "Please don't share card numbers, PINs, CVVs, passwords or codes here.",
      placeholder: "Type your question",
      send: "Send",
      person: "Talk to a person",
      close: "Close",
      source: "Source:",
      tooLong: "Your message is too long. Please keep it under 1,000 characters.",
      network: "I couldn't reach the server. Check that app.py is running and try again.",
      counter: "{n}/1000"
    },
    es: {
      launcher: "Chat de ayuda",
      title: "Chat de ayuda de Puentara",
      fictional: "Puentara es una empresa ficticia. Solo es una demo.",
      demo: "modo demo: respuestas de ejemplo",
      greeting: "¡Hola! Respondo preguntas con el centro de ayuda de Puentara, en español o en inglés. " +
        "Por favor, no compartas aquí números de tarjeta, PIN, CVV, contraseñas ni códigos.",
      placeholder: "Escribe tu pregunta",
      send: "Enviar",
      person: "Hablar con una persona",
      close: "Cerrar",
      source: "Fuente:",
      tooLong: "Tu mensaje es muy largo. Escríbelo en menos de 1000 caracteres.",
      network: "No pude conectarme con el servidor. Revisa que app.py esté corriendo e inténtalo de nuevo.",
      counter: "{n}/1000"
    }
  };
  var MAX_CHARS = 1000;
  var MAX_HISTORY = 20;

  var script = document.currentScript;
  var base = script && script.src ? new URL(script.src).origin : "";
  var lang = (navigator.language || "en").toLowerCase().indexOf("es") === 0 ? "es" : "en";
  var history = [];   // [{role, text, action}], sent with every message (the server keeps no state)
  var busy = false;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  var css = el("link");
  css.rel = "stylesheet";
  css.href = base + "/widget.css";
  document.head.appendChild(css);

  var launcher = el("button", "pw-launcher");
  var panel = el("section", "pw-panel");
  panel.hidden = true;
  var header = el("header", "pw-header");
  var title = el("h2", "pw-title");
  var langButton = el("button", "pw-lang");
  var closeButton = el("button", "pw-close", "×");
  var fictional = el("p", "pw-fictional");
  var badge = el("p", "pw-badge");
  badge.hidden = true;
  var log = el("div", "pw-log");
  log.setAttribute("aria-live", "polite");
  var personButton = el("button", "pw-person");
  var form = el("form", "pw-form");
  var input = el("textarea", "pw-input");
  input.rows = 2;
  input.maxLength = MAX_CHARS;
  var counter = el("span", "pw-counter");
  var sendButton = el("button", "pw-send");
  sendButton.type = "submit";

  header.append(title, langButton, closeButton);
  form.append(input, sendButton);
  panel.append(header, fictional, badge, log, personButton, form, counter);
  document.body.append(launcher, panel);

  var greeting = null;

  function applyLanguage() {
    var s = STRINGS[lang];
    launcher.textContent = s.launcher;
    title.textContent = s.title;
    langButton.textContent = lang === "en" ? "ES" : "EN";
    langButton.setAttribute("aria-label", lang === "en" ? "Español" : "English");
    closeButton.setAttribute("aria-label", s.close);
    fictional.textContent = s.fictional;
    badge.textContent = s.demo;
    personButton.textContent = s.person;
    input.placeholder = s.placeholder;
    sendButton.textContent = s.send;
    counter.textContent = s.counter.replace("{n}", input.value.length);
    if (greeting) greeting.textContent = s.greeting;
    panel.lang = lang;
  }

  function addBubble(role, text) {
    var bubble = el("div", "pw-msg pw-" + role);
    bubble.appendChild(el("p", "pw-text", text));
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
    return bubble;
  }

  function showReply(data) {
    var s = STRINGS[data.reply_lang] || STRINGS[lang];
    var bubble = addBubble("bot", data.reply);
    if (data.source) {
      var line = el("p", "pw-source", s.source + " ");
      var link = el("a", "", data.source.id + " · " + data.source.title);
      link.href = base + data.source.url;
      link.target = "_blank";
      link.rel = "noopener";
      line.appendChild(link);
      bubble.appendChild(line);
    }
    if (data.offer_handoff) {
      var offer = el("button", "pw-offer", s.person);
      offer.type = "button";
      offer.addEventListener("click", askForPerson);
      bubble.appendChild(offer);
    }
    if (data.demo) badge.hidden = false;
    log.scrollTop = log.scrollHeight;  // again, now that the source and button are in
    history.push({ role: "bot", text: data.reply, action: data.action });
  }

  function post(path, body) {
    busy = true;
    sendButton.disabled = personButton.disabled = true;
    return fetch(base + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) {
          var message = data && data.message ? data.message[lang] : STRINGS[lang].network;
          addBubble("error", message);
          return;
        }
        showReply(data);
      });
    }).catch(function () {
      addBubble("error", STRINGS[lang].network);
    }).then(function () {
      busy = false;
      sendButton.disabled = personButton.disabled = false;
    });
  }

  function send(event) {
    event.preventDefault();
    var text = input.value.trim();
    if (!text || busy) return;
    if (text.length > MAX_CHARS) {
      addBubble("error", STRINGS[lang].tooLong);
      return;
    }
    addBubble("customer", text);
    var sentHistory = history.slice(-MAX_HISTORY);
    history.push({ role: "customer", text: text });
    input.value = "";
    counter.textContent = STRINGS[lang].counter.replace("{n}", 0);
    post("/api/chat", { message: text, history: sentHistory, ui_lang: lang });
  }

  function askForPerson() {
    if (busy) return;
    addBubble("customer", "[" + STRINGS[lang].person + "]");
    post("/api/handoff", { history: history.slice(-MAX_HISTORY), ui_lang: lang });
  }

  form.addEventListener("submit", send);
  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) send(event);
  });
  input.addEventListener("input", function () {
    counter.textContent = STRINGS[lang].counter.replace("{n}", input.value.length);
  });
  personButton.type = "button";
  personButton.addEventListener("click", askForPerson);
  langButton.type = "button";
  langButton.addEventListener("click", function () {
    lang = lang === "en" ? "es" : "en";
    applyLanguage();
  });
  launcher.type = "button";
  launcher.addEventListener("click", function () {
    panel.hidden = false;
    launcher.hidden = true;
    input.focus();
  });
  closeButton.type = "button";
  closeButton.addEventListener("click", function () {
    panel.hidden = true;
    launcher.hidden = false;
  });

  greeting = addBubble("bot", "").firstChild;
  applyLanguage();

  // Show the demo badge from the start when the server runs without a key.
  fetch(base + "/api/status").then(function (r) { return r.json(); }).then(function (status) {
    badge.hidden = !status.demo;
  }).catch(function () { /* the first message will show the network error */ });

  // Small hook for the docs screenshot and manual testing: /?open opens the chat.
  if (/[?&]open\b/.test(window.location.search)) launcher.click();
})();
