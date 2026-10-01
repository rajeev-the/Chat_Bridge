"""
Claude share-link importer
--------------------------
Turns a Claude public share (https://claude.ai/share/<id>) into
{"title", "messages": [{"role": "user"|"assistant", "text": "..."}]}.

How it works:
  The share page HTML is an empty shell. In the browser it loads the chat from
      https://claude.ai/api/chat_snapshots/<id>?rendering_mode=messages&render_all_tools=true
  which returns JSON. We parse that JSON.

  The parser is deliberately tolerant: it searches the JSON for the list of
  messages (objects with a "sender" field) instead of assuming exact nesting,
  so small format changes don't break it.

Note: this is an internal endpoint, not an official API. It may change, and it
may be protected by Cloudflare against automated requests.
"""

import json
import re

SHARE_ID_RE = re.compile(r"claude\.ai/share/([0-9a-fA-F-]{36})")


class ClaudeShareError(Exception):
    pass


def snapshot_url(share_url_or_id: str) -> str:
    m = SHARE_ID_RE.search(share_url_or_id)
    share_id = m.group(1) if m else share_url_or_id.strip()
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", share_id):
        raise ClaudeShareError(f"Not a Claude share link or id: {share_url_or_id}")
    return (f"https://claude.ai/api/chat_snapshots/{share_id}"
            "?rendering_mode=messages&render_all_tools=true")


def _find_messages(obj):
    """Return the first list whose items are dicts with a 'sender' field."""
    stack = [obj]
    while stack:
        cur = stack.pop(0)
        if isinstance(cur, list):
            if cur and all(isinstance(x, dict) and "sender" in x for x in cur):
                return cur
            stack.extend(cur)
        elif isinstance(cur, dict):
            # check the usual key first
            if isinstance(cur.get("chat_messages"), list):
                stack.insert(0, cur["chat_messages"])
            stack.extend(v for k, v in cur.items() if k != "chat_messages")
    return None


def _title(data) -> str:
    if isinstance(data, dict):
        for key in ("snapshot_name", "name", "title", "conversation_name"):
            if isinstance(data.get(key), str) and data[key].strip():
                return data[key].strip()
        for v in data.values():
            if isinstance(v, dict):
                t = _title(v)
                if t != "(untitled)":
                    return t
    return "(untitled)"


def _message_text(msg: dict) -> str:
    parts = []
    content = msg.get("content")
    if isinstance(content, list) and content:
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text" and block.get("text"):
                parts.append(block["text"])
            # skip "thinking", "tool_use", "tool_result", "token_budget", etc.
    elif isinstance(msg.get("text"), str):
        parts.append(msg["text"])

    # note attached files/images so context isn't silently lost
    for key in ("attachments", "files", "files_v2"):
        for att in msg.get(key) or []:
            if isinstance(att, dict):
                name = att.get("file_name") or att.get("name")
                if name:
                    parts.append(f"[attached: {name}]")
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def parse_snapshot(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("<"):
        low = text.lower()
        if "just a moment" in low or "cf-chl" in low and "shared via claude" not in low:
            raise ClaudeShareError(
                "Got a Cloudflare challenge page instead of the chat. Automated requests "
                "were blocked; open the link in a real browser (e.g. Playwright) instead."
            )
        raise ClaudeShareError(
            "This is the Claude share *page*, which has no messages in it. Fetch the JSON "
            "from https://claude.ai/api/chat_snapshots/<share-id>?rendering_mode=messages"
            "&render_all_tools=true (or pass the share URL itself to import_chat.py, "
            "which does this for you)."
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ClaudeShareError(f"Response is not valid JSON: {e}") from None

    msgs = _find_messages(data)
    if msgs is None:
        raise ClaudeShareError("No messages found in the snapshot JSON.")

    if all("index" in m for m in msgs):
        msgs = sorted(msgs, key=lambda m: m["index"])

    messages = []
    for m in msgs:
        sender = m.get("sender")
        role = "user" if sender == "human" else "assistant" if sender == "assistant" else None
        if not role:
            continue
        t = _message_text(m)
        if t:
            messages.append({"role": role, "text": t})

    return {
        "source": "claude",
        "title": _title(data),
        "model": data.get("model") if isinstance(data, dict) else None,
        "created": data.get("created_at") if isinstance(data, dict) else None,
        "messages": messages,
    }
