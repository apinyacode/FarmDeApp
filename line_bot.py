"""LINE bot: lets people ask the Angel Arms helper questions in LINE.

- One-to-one chat with the LINE Official Account: every text message is answered.
- Group chats / multi-person chats: the bot answers only when it is @mentioned,
  or when a message starts with "bot" / "บอท" / "น้องบอท", so it stays quiet
  during normal conversation.

Needs LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN (in instance/.env), from
the LINE Developers console -> your Messaging API channel. Webhook URL:
    https://<your public address>/line/webhook

Messages are answered and forgotten: nothing from the chats is stored.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import urllib.error
import urllib.request

import chatbot

log = logging.getLogger(__name__)

REPLY_URL = "https://api.line.me/v2/bot/message/reply"
TRIGGER_WORDS = ("น้องบอท", "บอท", "bot")  # longest first
MAX_REPLY_CHARS = 4900  # LINE allows 5000 per text message
GROUP_HELLO = (
    "สวัสดีค่ะ! ถามเรื่องมูลนิธิในอ้อมกอดได้เลย โดยแท็ก @ ถึงฉัน หรือพิมพ์ \"บอท\" นำหน้าคำถาม\n"
    "Hello! Ask me about The Angel Arms Foundation: @mention me or start your message with \"bot\"."
)

limiter = chatbot.RateLimiter(limit=30, window=600)


def is_enabled():
    return bool(os.environ.get("LINE_CHANNEL_SECRET") and os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"))


def signature_ok(body: bytes, signature: str) -> bool:
    """LINE signs every webhook with the channel secret; reject anything else."""
    secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature)


def question_from(event):
    """The question to answer, or None if the bot should stay quiet."""
    msg = event.get("message") or {}
    if event.get("type") != "message" or msg.get("type") != "text":
        return None
    text = msg.get("text", "")
    if (event.get("source") or {}).get("type", "user") == "user":
        return text.strip() or None  # one-to-one chat: always answer

    # Group or multi-person chat: only when @mentioned or addressed by name.
    mentionees = (msg.get("mention") or {}).get("mentionees") or []
    mine = [m for m in mentionees if m.get("isSelf")]
    if mine:
        for m in sorted(mine, key=lambda m: m.get("index", 0), reverse=True):
            i, n = m.get("index", 0), m.get("length", 0)
            text = text[:i] + text[i + n:]  # remove "@Angel Arms" from the question
        return text.strip() or None
    lowered = text.strip().lower()
    for word in TRIGGER_WORDS:
        if not lowered.startswith(word):
            continue
        after = lowered[len(word):len(word) + 1]
        if word.isascii() and after.isascii() and after.isalnum():
            continue  # "bottle..." is not "bot ..."
        rest = text.strip()[len(word):].lstrip(" ,:-")
        return rest or None
    return None


def reply(reply_token, text):
    """Send a reply through the LINE Messaging API (reply tokens are free to use)."""
    payload = json.dumps({
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:MAX_REPLY_CHARS]}],
    }).encode()
    request = urllib.request.Request(REPLY_URL, data=payload, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""),
    })
    try:
        with urllib.request.urlopen(request, timeout=10) as r:
            r.read()
    except urllib.error.HTTPError as e:
        log.error("LINE reply failed: %s %s", e.code, e.read()[:300])
    except urllib.error.URLError as e:
        log.error("LINE reply failed: %s", e.reason)


def handle_event(event):
    token = event.get("replyToken")
    if not token:
        return
    if event.get("type") == "join":  # added to a group
        reply(token, GROUP_HELLO)
        return
    question = question_from(event)
    if not question:
        return
    source = event.get("source") or {}
    chat_id = source.get("groupId") or source.get("roomId") or source.get("userId") or "?"
    if not limiter.allow(chat_id):
        reply(token, "ขออภัย มีคำถามเยอะเกินไป ลองใหม่อีกสักครู่นะคะ / Too many questions right now, please try again in a few minutes.")
        return
    reply(token, chatbot.ask(question))


def handle_body(body: bytes, run_in_background=True):
    """Answer each event. By default in a background thread, because LINE expects the
    webhook to respond within a few seconds and an answer can take longer."""
    try:
        events = json.loads(body.decode("utf-8")).get("events", [])
    except (ValueError, UnicodeDecodeError):
        return

    def work():
        for event in events:
            try:
                handle_event(event)
            except Exception:  # never let one bad event stop the others
                log.exception("LINE event failed")

    if run_in_background:
        threading.Thread(target=work, daemon=True).start()
    else:
        work()
