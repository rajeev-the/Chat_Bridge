"""
ChatGPT share-link importer
---------------------------
Turns a ChatGPT public share page (https://chatgpt.com/share/<id>) into a
clean list of messages: [{"role": "user"|"assistant", "text": "..."}].

How it works:
  The share page HTML embeds the conversation in a script call:
      window.__reactRouterContext.streamController.enqueue("<payload>")
  The payload is React Router "turbo-stream" data: one flat JSON array where
  objects look like {"_12": 34} meaning  key = arr[12], value = decode(arr[34]).
  We decode it, find the conversation data, and walk `linear_conversation`.

Usage:
  python chatgpt_share.py page.html              # Markdown to stdout
  python chatgpt_share.py page.html --json       # JSON to stdout
  python chatgpt_share.py https://chatgpt.com/share/<id>   # fetch then parse

Note: this embedded format is not an official API. OpenAI can change it at any
time, so keep a fallback (paste text / upload export) in your platform.
"""

import json
import re
import sys
from datetime import datetime, timezone

# turbo-stream special constants (negative indices)
_SPECIAL = {
    -1: None,             # hole / undefined
    -2: float("nan"),
    -3: float("-inf"),
    -4: -0.0,
    -5: None,             # null
    -6: float("inf"),
    -7: None,             # undefined
}

_ENQUEUE_RE = re.compile(r'streamController\.enqueue\(("(?:[^"\\]|\\.)*")\)', re.S)


class ShareParseError(Exception):
    pass


# ---------------------------------------------------------------- decoding

def extract_payload(html_or_payload: str) -> list:
    """Get the turbo-stream array from page HTML, an enqueue(...) line, or raw JSON."""
    text = html_or_payload.strip()
    chunks = _ENQUEUE_RE.findall(text)
    if chunks:
        stream = "".join(json.loads(c) for c in chunks)
    elif text.startswith("["):
        stream = text
    else:
        raise ShareParseError(
            "No conversation data found. The page format may have changed, "
            "or the link is private/expired."
        )
    first_line = stream.split("\n", 1)[0]
    data = json.loads(first_line)
    if not isinstance(data, list) or not data:
        raise ShareParseError("Unexpected payload shape.")
    return data


def decode(arr: list):
    """Decode a turbo-stream flat array into normal Python objects."""
    cache: dict[int, object] = {}

    def val(i):
        if isinstance(i, int) and i < 0:
            return _SPECIAL.get(i)
        if i in cache:
            return cache[i]
        raw = arr[i]

        if isinstance(raw, dict):
            obj: dict = {}
            cache[i] = obj  # set before recursing (handles cycles / shared refs)
            for k, v in raw.items():
                key = arr[int(k[1:])] if k.startswith("_") and k[1:].isdigit() else k
                obj[key] = val(v)
            return obj

        if isinstance(raw, list):
            if raw and isinstance(raw[0], str):  # typed value: ["D", ts], ["P", id], ...
                tag = raw[0]
                if tag == "D" and len(raw) > 1:
                    out = datetime.fromtimestamp(raw[1] / 1000, tz=timezone.utc).isoformat()
                elif tag in ("P", "Z"):  # promise / not-yet-streamed value
                    out = None
                elif tag == "Y":  # symbol
                    out = raw[1] if len(raw) > 1 else None
                else:
                    out = raw
                cache[i] = out
                return out
            lst: list = []
            cache[i] = lst
            lst.extend(val(x) for x in raw)
            return lst

        cache[i] = raw  # string / number / bool / null
        return raw

    return val(0)


# ---------------------------------------------------------------- extraction

def _find_conversation(obj):
    """Locate the dict that has a 'mapping' or 'linear_conversation' (route names may change)."""
    stack = [obj]
    seen = set()
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, dict):
            if "linear_conversation" in cur or ("mapping" in cur and "title" in cur):
                return cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def _message_text(msg: dict) -> str:
    content = msg.get("content") or {}
    if content.get("content_type") not in ("text", "multimodal_text"):
        return ""  # skip thoughts, reasoning recaps, tool output, context blocks
    out = []
    for p in content.get("parts") or []:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, dict) and p.get("content_type") == "image_asset_pointer":
            out.append("[image]")
    return "\n".join(out).strip()


def _clean(text: str) -> str:
    # ChatGPT inline citation / widget markers, e.g. "fileciteturn5file0L5-L10", "genui{...}"
    text = re.sub(r".*?", "", text)
    text = re.sub(r"file?cite(?:turn\d+file\d+(?:L\d+-L\d+)?)+", "", text)
    text = re.sub(r"genui\{.*?\}\}", "", text)
    return text.strip()


def _nodes_in_order(conv: dict) -> list:
    if conv.get("linear_conversation"):
        return conv["linear_conversation"]
    mapping = conv.get("mapping") or {}
    node_id, chain, seen = conv.get("current_node"), [], set()
    while node_id and node_id in mapping and node_id not in seen:
        seen.add(node_id)
        chain.append(mapping[node_id])
        node_id = mapping[node_id].get("parent")
    return list(reversed(chain))


def parse_share(html_or_payload: str) -> dict:
    root = decode(extract_payload(html_or_payload))
    conv = _find_conversation(root)
    if not conv:
        raise ShareParseError("Conversation data not found in payload.")

    messages = []
    for node in _nodes_in_order(conv):
        msg = (node or {}).get("message") or {}
        role = (msg.get("author") or {}).get("role")
        if role not in ("user", "assistant"):
            continue
        if (msg.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
            continue
        text = _clean(_message_text(msg))
        if text:
            messages.append({"role": role, "text": text})

    return {
        "source": "chatgpt",
        "title": conv.get("title") or "(untitled)",
        "model": conv.get("default_model_slug"),
        "created": conv.get("create_time"),
        "messages": messages,
    }


def to_markdown(chat: dict) -> str:
    lines = [f"# {chat['title']}", ""]
    for m in chat["messages"]:
        lines.append(f"**{'You' if m['role'] == 'user' else 'ChatGPT'}:**\n\n{m['text']}\n")
    return "\n".join(lines)


def fetch(url: str) -> str:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    raw = fetch(src) if src.startswith("http") else open(src, encoding="utf-8").read()
    chat = parse_share(raw)
    if "--json" in sys.argv:
        print(json.dumps(chat, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(chat))
