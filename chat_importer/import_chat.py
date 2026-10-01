"""
import_chat.py — one importer for ChatGPT and Claude share links
----------------------------------------------------------------
Every source comes out in the same shape:
    {"source": "chatgpt"|"claude", "title": str, "messages": [{"role", "text"}]}

Examples:
  # one link
  python import_chat.py https://chatgpt.com/share/<id>
  python import_chat.py https://claude.ai/share/<id>

  # saved files work too (from Postman / browser "Save as")
  python import_chat.py chatgpt_page.html
  python import_chat.py claude_snapshot.json

  # merge several chats into one conversation (the core of your platform)
  python import_chat.py <link1> <link2> <file3> --merge --json > merged.json

In code:
  from import_chat import import_source, merge
  chats = [import_source(x) for x in links]
  combined = merge(chats)
"""

import json
import sys
import urllib.error
import urllib.request

from chatgpt_share import ShareParseError, parse_share as parse_chatgpt
from claude_share import ClaudeShareError, parse_snapshot as parse_claude, snapshot_url

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}


class ImportError_(Exception):
    pass


def detect_source(src: str, content: str | None = None) -> str:
    s = src.lower()
    if "chatgpt.com" in s or "chat.openai.com" in s:
        return "chatgpt"
    if "claude.ai" in s:
        return "claude"
    if content is not None:
        if "streamController.enqueue" in content or content.lstrip().startswith("[{"):
            return "chatgpt"
        if ('"sender"' in content or "chat_messages" in content
                or "Shared via Claude" in content or "api/chat_snapshots" in content):
            return "claude"
    raise ImportError_(f"Can't tell whether this is a ChatGPT or Claude chat: {src}")


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        hint = (" — likely bot protection (Cloudflare). Try from a normal network, "
                "use a real browser (Playwright), or save the page/JSON manually.") \
            if e.code in (403, 429, 503) else ""
        raise ImportError_(f"HTTP {e.code} fetching {url}{hint}") from None
    except urllib.error.URLError as e:
        raise ImportError_(f"Could not reach {url}: {e.reason}") from None


def import_source(src: str) -> dict:
    """Import one chat from a share URL or a saved file."""
    try:
        if src.startswith("http"):
            kind = detect_source(src)
            if kind == "chatgpt":
                return parse_chatgpt(_fetch(src))
            return parse_claude(_fetch(snapshot_url(src)))

        with open(src, encoding="utf-8") as f:
            content = f.read()
        kind = detect_source(src, content)
        return parse_chatgpt(content) if kind == "chatgpt" else parse_claude(content)
    except (ShareParseError, ClaudeShareError) as e:
        raise ImportError_(f"{src}: {e}") from None


def merge(chats: list[dict], title: str | None = None) -> dict:
    """Combine several imported chats into one ordered conversation.

    Each message keeps where it came from, so a model continuing the chat
    (e.g. via /claude or /gpt) can see which assistant said what.
    """
    messages = []
    for i, chat in enumerate(chats, 1):
        label = {"chatgpt": "ChatGPT", "claude": "Claude"}.get(chat["source"], chat["source"])
        messages.append({
            "role": "system",
            "text": f"--- Imported chat {i}: \"{chat['title']}\" from {label} ---",
            "source": chat["source"],
        })
        for m in chat["messages"]:
            messages.append({**m, "source": chat["source"], "chat_title": chat["title"]})
    return {
        "title": title or " + ".join(c["title"] for c in chats),
        "sources": [{"source": c["source"], "title": c["title"],
                     "message_count": len(c["messages"])} for c in chats],
        "messages": messages,
    }


def to_markdown(conv: dict) -> str:
    names = {"chatgpt": "ChatGPT", "claude": "Claude"}
    out = [f"# {conv['title']}", ""]
    for m in conv["messages"]:
        if m["role"] == "system":
            out.append(f"\n_{m['text']}_\n")
        elif m["role"] == "user":
            out.append(f"**You:**\n\n{m['text']}\n")
        else:
            out.append(f"**{names.get(m.get('source'), 'Assistant')}:**\n\n{m['text']}\n")
    return "\n".join(out)


def to_prompt_messages(conv: dict) -> list[dict]:
    """Shape a merged conversation for any chat API (Claude / OpenAI / Gemini).

    Prior assistant turns from *other* models are labelled so the model you
    call next knows it didn't write them.
    """
    names = {"chatgpt": "ChatGPT", "claude": "Claude"}
    msgs = []
    for m in conv["messages"]:
        if m["role"] == "system":
            msgs.append({"role": "user", "content": m["text"]})
        elif m["role"] == "user":
            msgs.append({"role": "user", "content": m["text"]})
        else:
            who = names.get(m.get("source"), "an assistant")
            msgs.append({"role": "assistant", "content": f"[{who}]: {m['text']}"})
    # most chat APIs need alternating roles: join consecutive same-role turns
    merged = []
    for m in msgs:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n\n" + m["content"]
        else:
            merged.append(dict(m))
    return merged


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    try:
        chats = [import_source(a) for a in args]
    except ImportError_ as e:
        sys.exit(f"Error: {e}")

    result = merge(chats) if ("--merge" in sys.argv or len(chats) > 1) else chats[0]
    if "--json" in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif "messages" in result and "sources" in result:
        print(to_markdown(result))
    else:
        print(to_markdown(merge([result], title=result["title"])))
