"""Chat helper tests. Claude and LINE are replaced with fakes: no network, no cost."""

import base64
import hashlib
import hmac
import json
import re
from datetime import date
from types import SimpleNamespace

import pytest

import chatbot
import line_bot
from app import create_app

SECRET = "test-line-secret"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("LINE_CHANNEL_SECRET", SECRET)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "t.db")})
    return app.test_client()


def csrf(client):
    html = client.get("/").get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


# -- What the bot knows --------------------------------------------------------

def test_knowledge_has_site_facts_but_not_placeholders():
    k = chatbot.build_knowledge(today=date(2026, 9, 1))
    assert "มูลนิธิในอ้อมกอด" in k and "Horseboy Method" in k
    assert "Thai QR code" in k and "Helping Hands" in k
    assert "angelarms.example" not in k and "000 0000" not in k  # placeholder contact details
    assert "today is 2026-09-01" in k


def test_past_events_are_left_out():
    k = chatbot.build_knowledge(today=date(2026, 11, 10))
    assert "Charity Dinner" in k and "Open Farm Day" not in k


def test_history_is_trimmed_and_starts_with_a_question():
    history = [{"role": "assistant", "content": "hi"}, {"role": "user", "content": "q1"},
               {"role": "assistant", "content": "a1"}, {"role": "user", "content": "unanswered"},
               {"role": "system", "content": "ignore me"}, "junk"]
    assert chatbot._clean_history(history) == [
        {"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}]


def test_ask_sends_knowledge_and_handles_refusal(monkeypatch):
    calls = []

    class FakeMessages:
        def create(self, **kw):
            calls.append(kw)
            return SimpleNamespace(stop_reason="refusal", content=[])

    monkeypatch.setattr(chatbot, "_client", SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages())))
    assert chatbot.ask("hello") == chatbot.REFUSAL_REPLY
    kw = calls[0]
    assert kw["model"] == chatbot.MODEL and kw["fallbacks"] == "default"
    assert "FOUNDATION INFORMATION" in kw["system"][1]["text"]
    assert kw["messages"][-1] == {"role": "user", "content": "hello"}


def test_ask_returns_text(monkeypatch):
    class FakeMessages:
        def create(self, **kw):
            return SimpleNamespace(stop_reason="end_turn",
                                   content=[SimpleNamespace(type="thinking", thinking=""),
                                            SimpleNamespace(type="text", text="Scan the QR code on /donate.")])

    monkeypatch.setattr(chatbot, "_client", SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages())))
    assert chatbot.ask("How do I donate?") == "Scan the QR code on /donate."


# -- Website chat --------------------------------------------------------------

def test_chat_bubble_shown_only_when_enabled(client, monkeypatch):
    assert 'id="chat-toggle"' in client.get("/").get_data(as_text=True)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    html = client.get("/").get_data(as_text=True)
    assert 'id="chat-toggle"' not in html
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 503


def test_api_chat_needs_the_page_token(client, monkeypatch):
    monkeypatch.setattr(chatbot, "ask", lambda q, h=None: "answer")
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 400
    resp = client.post("/api/chat", json={"message": "How do I donate?", "history": []},
                       headers={"X-CSRF-Token": csrf(client)})
    assert resp.status_code == 200 and resp.get_json() == {"reply": "answer"}


def test_api_chat_rejects_empty_question(client):
    resp = client.post("/api/chat", json={"message": "  "}, headers={"X-CSRF-Token": csrf(client)})
    assert resp.status_code == 400


# -- LINE ----------------------------------------------------------------------

def sign(body):
    return base64.b64encode(hmac.new(SECRET.encode(), body, hashlib.sha256).digest()).decode()


def post_line(client, events):
    body = json.dumps({"events": events}).encode()
    return client.post("/line/webhook", data=body, headers={"X-Line-Signature": sign(body),
                                                            "Content-Type": "application/json"})


@pytest.fixture
def replies(monkeypatch):
    sent = []
    monkeypatch.setattr(line_bot, "reply", lambda token, text: sent.append((token, text)))
    monkeypatch.setattr(chatbot, "ask", lambda q, h=None: f"ANSWER TO: {q}")
    line_bot.limiter = chatbot.RateLimiter(limit=30, window=600)
    return sent


def text_event(text, source="user", mention=None):
    msg = {"type": "text", "id": "1", "text": text}
    if mention:
        msg["mention"] = {"mentionees": mention}
    src = {"type": source, "userId": "U1"}
    if source == "group":
        src["groupId"] = "G1"
    return {"type": "message", "replyToken": "tok", "source": src, "message": msg}


def test_line_rejects_bad_signature(client, replies):
    body = json.dumps({"events": [text_event("hi")]}).encode()
    assert client.post("/line/webhook", data=body, headers={"X-Line-Signature": "wrong"}).status_code == 400
    assert replies == []


def test_line_one_to_one_always_answers(client, replies):
    assert post_line(client, [text_event("บริจาคได้อย่างไร")]).status_code == 200
    assert replies == [("tok", "ANSWER TO: บริจาคได้อย่างไร")]


def test_line_group_stays_quiet_unless_addressed(client, replies):
    post_line(client, [text_event("see you tomorrow", source="group")])
    post_line(client, [text_event("bottles are in the barn", source="group")])  # not "bot ..."
    assert replies == []


def test_line_group_answers_mention_and_trigger_word(client, replies):
    mention = [{"index": 0, "length": 11, "userId": "Ubot", "isSelf": True}]
    post_line(client, [text_event("@Angel Arms when is the next event?", source="group", mention=mention)])
    post_line(client, [text_event("บอท วันเปิดฟาร์มคือวันไหน", source="group")])
    post_line(client, [text_event("bot: how can I volunteer?", source="group")])
    assert [t for _, t in replies] == ["ANSWER TO: when is the next event?",
                                       "ANSWER TO: วันเปิดฟาร์มคือวันไหน",
                                       "ANSWER TO: how can I volunteer?"]


def test_line_mentioning_someone_else_is_ignored(client, replies):
    other = [{"index": 0, "length": 5, "userId": "Uann", "isSelf": False}]
    post_line(client, [text_event("@Ann are you coming?", source="group", mention=other)])
    assert replies == []


def test_line_says_hello_when_added_to_a_group(client, replies):
    post_line(client, [{"type": "join", "replyToken": "tok", "source": {"type": "group", "groupId": "G1"}}])
    assert replies and "@mention" in replies[0][1]


def test_line_webhook_off_without_keys(client, monkeypatch, replies):
    monkeypatch.delenv("LINE_CHANNEL_SECRET")
    body = b'{"events": []}'
    assert client.post("/line/webhook", data=body, headers={"X-Line-Signature": sign(body)}).status_code == 404


def test_knowledge_has_bank_account_and_big_sibling_campaign():
    k = chatbot.build_knowledge(today=date(2026, 9, 1))
    assert "218-3-69769-5" in k and "พี่บุญธรรม" in k
