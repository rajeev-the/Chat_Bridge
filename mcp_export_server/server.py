"""
ChatGPT History MCP Server
--------------------------
Exposes your exported ChatGPT conversations (conversations.json) to Claude
or any other MCP client.

Tools:
  - list_conversations(query, limit)   -> titles, ids, dates
  - get_conversation(conversation)     -> full chat as readable text
  - search_messages(query, limit)      -> matching snippets across all chats

Setup:
  1. ChatGPT -> Settings -> Data controls -> Export data, unzip it.
  2. Set CHATGPT_EXPORT to the path of conversations.json
     (or put conversations.json next to this file).
"""

import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("chatgpt-history")

DEFAULT_PATH = Path(__file__).parent / "conversations.json"


def _export_path() -> Path:
    return Path(os.environ.get("CHATGPT_EXPORT", DEFAULT_PATH)).expanduser()


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    path = _export_path()
    if not path.exists():
        raise FileNotFoundError(
            f"conversations.json not found at {path}. "
            "Set the CHATGPT_EXPORT environment variable to its location."
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("conversations", [])


def _fmt_time(ts) -> str:
    if not ts:
        return "unknown date"
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _text_of(message: dict) -> str:
    content = message.get("content") or {}
    parts = content.get("parts") or []
    out = []
    for p in parts:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, dict):
            # images/files show up as dicts; keep any text they carry
            if p.get("text"):
                out.append(p["text"])
            elif p.get("content_type"):
                out.append(f"[{p['content_type']}]")
    if not out and content.get("text"):
        out.append(content["text"])
    return "\n".join(out).strip()


def _thread(conv: dict) -> list[tuple[str, str]]:
    """Walk from current_node back to the root to get the visible thread."""
    mapping = conv.get("mapping") or {}
    node_id = conv.get("current_node")
    if not node_id and mapping:
        # fall back to the last node with no children
        leaves = [k for k, v in mapping.items() if not v.get("children")]
        node_id = leaves[-1] if leaves else None

    chain = []
    seen = set()
    while node_id and node_id in mapping and node_id not in seen:
        seen.add(node_id)
        node = mapping[node_id]
        msg = node.get("message")
        if msg:
            role = (msg.get("author") or {}).get("role", "unknown")
            text = _text_of(msg)
            hidden = (msg.get("metadata") or {}).get("is_visually_hidden_from_conversation")
            if text and role in ("user", "assistant") and not hidden:
                chain.append((role, text))
        node_id = node.get("parent")
    chain.reverse()
    return chain


def _conv_id(conv: dict, index: int) -> str:
    return conv.get("conversation_id") or conv.get("id") or f"idx-{index}"


def _find(conversation: str) -> dict | None:
    convs = _load()
    key = conversation.strip().lower()
    for i, c in enumerate(convs):
        if _conv_id(c, i).lower() == key:
            return c
    for c in convs:  # exact title
        if (c.get("title") or "").strip().lower() == key:
            return c
    for c in convs:  # partial title
        if key in (c.get("title") or "").lower():
            return c
    return None


@mcp.tool()
def list_conversations(query: str = "", limit: int = 30) -> str:
    """List ChatGPT conversations, newest first. Optionally filter by a word in the title."""
    convs = list(enumerate(_load()))
    convs.sort(key=lambda ic: ic[1].get("update_time") or ic[1].get("create_time") or 0, reverse=True)
    q = query.lower().strip()
    rows = []
    for i, c in convs:
        title = c.get("title") or "(untitled)"
        if q and q not in title.lower():
            continue
        rows.append(f"- {title}  |  id: {_conv_id(c, i)}  |  {_fmt_time(c.get('update_time') or c.get('create_time'))}")
        if len(rows) >= limit:
            break
    if not rows:
        return "No conversations matched."
    return f"{len(rows)} conversation(s):\n" + "\n".join(rows)


@mcp.tool()
def get_conversation(conversation: str, max_chars: int = 60000) -> str:
    """Return a full ChatGPT conversation as text. Pass its id or (part of) its title."""
    c = _find(conversation)
    if not c:
        return f"No conversation found for '{conversation}'. Try list_conversations first."
    lines = [f"# {c.get('title') or '(untitled)'}", f"Created: {_fmt_time(c.get('create_time'))}", ""]
    for role, text in _thread(c):
        speaker = "User" if role == "user" else "ChatGPT"
        lines.append(f"**{speaker}:**\n{text}\n")
    out = "\n".join(lines)
    if len(out) > max_chars:
        out = out[:max_chars] + f"\n\n[...truncated at {max_chars} characters]"
    return out


@mcp.tool()
def search_messages(query: str, limit: int = 20) -> str:
    """Search the text of every message across all ChatGPT conversations."""
    q = query.lower().strip()
    if not q:
        return "Please give a search term."
    hits = []
    for i, c in enumerate(_load()):
        for role, text in _thread(c):
            pos = text.lower().find(q)
            if pos == -1:
                continue
            start, end = max(0, pos - 120), min(len(text), pos + len(q) + 120)
            snippet = text[start:end].replace("\n", " ")
            hits.append(
                f"- [{c.get('title') or '(untitled)'}] (id: {_conv_id(c, i)}) "
                f"{'User' if role == 'user' else 'ChatGPT'}: …{snippet}…"
            )
            if len(hits) >= limit:
                return "\n".join(hits)
    return "\n".join(hits) if hits else "No messages matched."


if __name__ == "__main__":
    mcp.run()
