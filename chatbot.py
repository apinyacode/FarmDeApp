"""The Angel Arms helper: answers visitors' questions using the site's own content.

Used by both the website chat bubble (/api/chat) and the LINE bot
(/line/webhook). It only knows what is in data/*.json, so updating the site's
content also updates what the bot says.

Needs ANTHROPIC_API_KEY (in instance/.env). Without it the chat is switched off.
"""

import json
import logging
import os
import threading
import time
from datetime import date
from pathlib import Path

import anthropic

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
MODEL = os.environ.get("CHATBOT_MODEL", "claude-opus-5")
MAX_QUESTION_CHARS = 1000
MAX_HISTORY_TURNS = 6  # earlier questions/answers sent along for context (website only)

INSTRUCTIONS = """You are the friendly helper for The Angel Arms Foundation (มูลนิธิในอ้อมกอด), \
answering questions from visitors on the foundation's website and in LINE chats.

How to answer:
- Use only the foundation information given below. If the answer isn't there, say you \
don't know and point the person to the contact details or the Facebook page. Never guess \
dates, prices, amounts, names or bank details.
- Reply in the same language the person wrote in (Thai or English).
- Keep answers short and warm: usually 2 to 5 sentences. Use plain text only, no markdown, \
no tables, because replies are shown in a small chat window and in LINE.
- When it helps, point to the right page on the website: /about, /events, /volunteer, /donate.
- For donations, explain the Thai QR code and the two funds on the Donate page. Never ask for \
card numbers or send anyone a different payment method.
- Do not ask for or collect personal details (ID numbers, addresses, health information). \
For volunteering, send people to the sign-up form on /volunteer.
- Do not give medical, therapy or veterinary advice about a specific child or horse. Explain \
what the foundation offers in general and suggest contacting the team.
- If someone is rude or asks about unrelated topics, politely steer back to the foundation."""


# ---------------------------------------------------------------------------
# What the bot knows: built from the site's own content files
# ---------------------------------------------------------------------------

def _load(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _is_placeholder(value):
    """Contact details that are still the example placeholders shouldn't be given out."""
    v = (value or "").strip()
    return not v or v.endswith(".example") or "000 0000" in v or "000-0-00000" in v


def build_knowledge(today=None):
    """Plain-text summary of everything on the site, for the bot to answer from."""
    today = today or date.today()
    site = _load("site.json")
    events = _load("events.json")
    opportunities = _load("opportunities.json")
    programs = _load("programs.json")
    lines = []
    add = lines.append

    add(f"FOUNDATION: {site['name']} (Thai name: {site.get('name_th', '')})")
    add(f"Tagline: {site.get('headline', '')}. {site.get('headline_sub', '')}")
    add(f"Vision: {site['vision']}")
    add(f"Mission: {site['mission']}")
    add(f"Method: {site.get('method', '')}")
    add("Background:")
    lines += [f"- {p}" for p in site.get("background", [])]
    add("Objectives:")
    lines += [f"{i}. {o}" for i, o in enumerate(site.get("objectives", []), 1)]
    add("What we do:")
    for p in site.get("programs", []):
        add(f"- {p['title']}: {p['text']} " + "; ".join(p.get("points", [])))
    add("Values: " + "; ".join(f"{v['title']} - {v['text']}" for v in site.get("values", [])))
    add("How it works: " + " ".join(f"({i}) {s['title']}: {s['text']}"
                                   for i, s in enumerate(site["story"]["steps"], 1)))
    add("Guardian Angels (our horses): " + site["guardian_angels"]["intro"])
    add("Board and management: " + "; ".join(f"{b['name']} ({b['role']})" for b in site.get("board", [])))

    c = site["contact"]
    add("CONTACT:")
    add(f"- Address: {c.get('address', '')}")
    for label, key in (("Email", "email"), ("Phone", "phone")):
        if not _is_placeholder(c.get(key)):
            add(f"- {label}: {c[key]}")
    if c.get("facebook"):
        add(f"- Facebook page: {c['facebook']}")

    d = site["donation"]
    add("DONATING (page /donate):")
    for f in d["funds"]:
        examples = "; ".join(f"{e['amount']:,} {d['currency']} = {e['label']}" for e in f.get("examples", []))
        add(f"- {f['title']}: {f['text']} Examples: {examples}")
    qr = d.get("qr") or {}
    if qr:
        add(f"- Donate by scanning the Thai QR code on /donate with any Thai banking app and typing the "
            f"amount. Account name: {qr.get('account_name')}; bank: {qr.get('bank')}.")
    bt = d.get("bank_transfer", {})
    if bt.get("account_number") and not _is_placeholder(bt["account_number"]):
        add(f"- Bank transfer: {bt.get('bank')}, account {bt['account_number']}, name {bt.get('account_name')}.")
    if bt.get("note"):
        add(f"- {bt['note']}")
    add("- Gifts in kind we welcome: " + "; ".join(d.get("in_kind", [])))
    sp = site.get("sponsor")
    if sp:
        add(f"- Campaign '{sp['title']}' ({sp['title_th']}): {sp['text_th']} {sp['text']}")

    add("VOLUNTEERING (page /volunteer, sign-up form at /volunteer#signup):")
    add(programs.get("intro", ""))
    add("Key facts: " + "; ".join(f"{f['label']}: {f['value']}" for f in programs.get("facts", [])))
    for p in programs.get("programs", []):
        add(f"- 5-day program '{p['title']}': {p['tagline']} {p['how']} "
            f"Activities: {'; '.join(p.get('activities', []))}")
    add(programs.get("closing", ""))
    add("Regular volunteer roles:")
    for o in opportunities:
        add(f"- {o['title']} ({o['commitment']}): {o['description']} "
            f"Requirements: {', '.join(o.get('requirements', []))}")

    add(f"UPCOMING EVENTS (today is {today.isoformat()}; full calendar at /events):")
    upcoming = sorted((e for e in events if e["date"] >= today.isoformat()), key=lambda e: e["date"])
    if not upcoming:
        add("- No upcoming events are listed yet.")
    for e in upcoming:
        add(f"- {e['date']} {e['start']}-{e['end']}: {e['title']} at {e['location']}. {e['summary']}"
            + (" Volunteers needed." if e.get("volunteers_needed") else ""))

    return "\n".join(line for line in lines if line is not None)


# ---------------------------------------------------------------------------
# Asking Claude
# ---------------------------------------------------------------------------

REFUSAL_REPLY = ("Sorry, I can't help with that one. For anything else about the foundation, "
                 "our volunteers, horses or donations, just ask!")
ERROR_REPLY = ("Sorry, I'm having trouble answering right now. Please try again in a moment, "
               "or contact us through our Facebook page.")

_client = None


def is_enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CHATBOT_ENABLED") == "1")


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client


def _clean_history(history):
    """Keep the last few well-formed turns, starting with a question, oldest first."""
    turns = []
    for item in (history or [])[-MAX_HISTORY_TURNS * 2:]:
        if not isinstance(item, dict):
            continue
        role, text = item.get("role"), item.get("content")
        if role in ("user", "assistant") and isinstance(text, str) and text.strip():
            turns.append({"role": role, "content": text.strip()[:MAX_QUESTION_CHARS * 2]})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    # the question being asked now is added separately, so drop a trailing unanswered one
    while turns and turns[-1]["role"] != "assistant":
        turns.pop()
    return turns


def ask(question, history=None):
    """Answer one question. Returns plain text (never raises)."""
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if not question:
        return ""
    messages = _clean_history(history) + [{"role": "user", "content": question}]
    try:
        response = _get_client().beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            # Instructions + site knowledge are the same for every question: cache them.
            system=[{"type": "text", "text": INSTRUCTIONS},
                    {"type": "text", "text": "FOUNDATION INFORMATION:\n" + build_knowledge()}],
            cache_control={"type": "ephemeral"},
            # Short friendly answers don't need deep reasoning; keeps replies quick and cheap.
            output_config={"effort": "low"},
            # If the model declines a harmless question, let Anthropic retry on its recommended model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=messages,
        )
    except anthropic.RateLimitError:
        log.warning("chatbot: rate limited by the API")
        return ERROR_REPLY
    except anthropic.APIStatusError as e:
        log.error("chatbot: API error %s: %s", e.status_code, e.message)
        return ERROR_REPLY
    except anthropic.APIConnectionError:
        log.error("chatbot: could not reach the API")
        return ERROR_REPLY

    if response.stop_reason == "refusal":
        return REFUSAL_REPLY
    text = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return text or ERROR_REPLY


# ---------------------------------------------------------------------------
# Simple flood protection (per visitor / per LINE chat)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Allow at most `limit` questions per `window` seconds for each key."""

    def __init__(self, limit=20, window=600):
        self.limit, self.window = limit, window
        self._hits = {}
        self._lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True
