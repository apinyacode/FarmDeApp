// "Ask us" chat bubble: sends questions to /api/chat and shows the answers.
(function () {
  const $ = (id) => document.getElementById(id);
  const panel = $("chat-panel"), toggle = $("chat-toggle"), log = $("chat-log");
  const form = $("chat-form"), input = $("chat-input"), chips = $("chat-chips");
  if (!panel || !toggle) return;
  const token = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  const KEY = "angelarms-chat";
  let history = [];
  let busy = false;

  // Keep the conversation while the visitor moves between pages (this browser tab only).
  try { history = JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch (e) { history = []; }
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(history.slice(-12))); } catch (e) {} };

  function bubble(text, who) {
    const p = document.createElement("p");
    p.className = "bubble " + who;
    p.textContent = text; // plain text only, never HTML
    log.appendChild(p);
    log.scrollTop = log.scrollHeight;
    return p;
  }
  history.forEach((m) => bubble(m.content, m.role === "user" ? "me" : "bot"));
  if (history.length) chips.hidden = true;

  function open(show) {
    panel.hidden = !show;
    toggle.setAttribute("aria-expanded", String(show));
    toggle.classList.toggle("is-open", show);
    if (show) { input.focus(); log.scrollTop = log.scrollHeight; }
  }
  toggle.addEventListener("click", () => open(panel.hidden));
  $("chat-close").addEventListener("click", () => { open(false); toggle.focus(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) open(false); });

  async function send(question) {
    question = question.trim();
    if (!question || busy) return;
    busy = true;
    chips.hidden = true;
    bubble(question, "me");
    const waiting = bubble("…", "bot typing");
    let answer;
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
        body: JSON.stringify({ message: question, history: history }),
      });
      const data = await res.json().catch(() => ({}));
      answer = data.reply || data.error || "Sorry, something went wrong. Please try again.";
    } catch (e) {
      answer = "Sorry, I couldn't connect. Please check your internet and try again.";
    }
    waiting.remove();
    bubble(answer, "bot");
    history.push({ role: "user", content: question }, { role: "assistant", content: answer });
    save();
    busy = false;
    input.focus();
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); const q = input.value; input.value = ""; send(q); });
  chips.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => send(b.textContent)));
})();
