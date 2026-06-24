"""
Slack bot for the INSART Knowledge Base.

Supported interactions:
  /kb <question>        — slash command, answers in the channel
  @KBBot <question>     — app mention, replies in thread
  DM the bot            — direct message, answers in the DM

Required env vars:
  SLACK_BOT_TOKEN       — Bot User OAuth Token (xoxb-...)
  SLACK_SIGNING_SECRET  — from the Slack app's Basic Information page
  KB_BASE_URL           — public URL of this app, e.g. https://insart-kb.vercel.app
"""

import os
import re
import threading

from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler


bolt_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
    process_before_response=True,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _ask(question: str):
    from app import _do_ask
    return _do_ask(question)


def _full_url(path: str) -> str:
    base = os.environ.get("KB_BASE_URL", "").rstrip("/")
    return f"{base}{path}" if base else path


def _build_blocks(answer: str, sources: list) -> list:
    blocks = []

    if answer:
        top_conf = sources[0].get("confidence", 0) if sources else 0
        conf_text = f"  _{top_conf}% match_" if top_conf else ""
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":sparkles: *AI Answer*{conf_text}\n{answer}",
            },
        })

    if sources:
        lines = []
        for s in sources[:5]:
            url = _full_url(s["url"])
            conf = s.get("confidence", 0)
            conf_text = f" `{conf}%`" if conf else ""
            lines.append(f"• <{url}|{s['title']}>{conf_text}  _{s['crumb']}_")

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Sources:*\n" + "\n".join(lines),
            },
        })

        first_url = _full_url(sources[0]["url"])
        blocks.append({
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": f"Open: {sources[0]['title'][:40]}"},
                "url": first_url,
                "action_id": "open_first_source",
            }],
        })

    return blocks


def _run_and_respond(question: str, send_fn, response_type: str = "in_channel", thread_ts: str = None):
    """Run _do_ask in a thread and send the result via send_fn."""
    def _work():
        answer, sources, error = _ask(question)

        if error and not sources:
            send_fn({"text": f":x: {error}"})
            return

        kwargs = {
            "text": answer or "Here's what I found in the knowledge base.",
            "blocks": _build_blocks(answer, sources),
        }
        if response_type:
            kwargs["response_type"] = response_type
        if thread_ts:
            kwargs["thread_ts"] = thread_ts

        send_fn(kwargs)

    threading.Thread(target=_work, daemon=True).start()


# ── slash command: /kb <question> ─────────────────────────────────────────────

@bolt_app.command("/kb")
def handle_kb_command(ack, respond, command):
    ack()
    q = command["text"].strip()
    if not q:
        respond({"text": "Usage: `/kb your question here`\nExample: `/kb Do we have banking fintech cases?`"})
        return
    respond({"response_type": "ephemeral", "text": ":hourglass: Searching the knowledge base…"})
    _run_and_respond(q, respond, response_type="in_channel")


# ── app mention: @KBBot <question> ────────────────────────────────────────────

@bolt_app.event("app_mention")
def handle_mention(event, say):
    q = re.sub(r"<@[A-Z0-9]+>", "", event["text"]).strip()
    if not q:
        say("Hi! Ask me anything from the INSART Knowledge Base.\nExample: `@KBBot Do we have banking fintech cases?`")
        return
    thread_ts = event.get("thread_ts") or event.get("ts")
    _run_and_respond(q, say, response_type=None, thread_ts=thread_ts)


# ── direct message ────────────────────────────────────────────────────────────

@bolt_app.event("message")
def handle_dm(event, say):
    if event.get("channel_type") != "im" or event.get("subtype"):
        return
    q = event.get("text", "").strip()
    if not q:
        return
    _run_and_respond(q, say, response_type=None)


# ── Bolt → Flask adapter ──────────────────────────────────────────────────────

handler = SlackRequestHandler(bolt_app)
