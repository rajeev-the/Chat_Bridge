"""Tests for the ChatGPT and Claude share importers.

Run:  pip install pytest && pytest
The fixtures here are built in the same formats as the real share pages.
Add real saved responses to tests/fixtures/ to test against live formats.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "chat_importer"))

from chatgpt_share import parse_share  # noqa: E402
from claude_share import snapshot_url  # noqa: E402
from import_chat import ImportError_, import_source, merge, to_prompt_messages  # noqa: E402


# ---------------------------------------------------------------- fixtures

def _encode_turbo_stream(root):
    """Encode a Python object the way React Router turbo-stream does (flat array, keys by index)."""
    arr, idx = [], {}

    def put(v):
        if v is None:
            return -5
        if isinstance(v, (str, int, float, bool)):
            key = (type(v).__name__, v)
            if key in idx:
                return idx[key]
            idx[key] = len(arr)
            arr.append(v)
            return idx[key]
        i = len(arr)
        arr.append(None)
        if isinstance(v, tuple):  # typed value, e.g. ("P", 5) = promise
            arr[i] = list(v)
            return i
        if isinstance(v, list):
            arr[i] = [put(x) for x in v]
            return i
        arr[i] = {f"_{put(k)}": put(val) for k, val in v.items()}
        return i

    put(root)
    return arr


def _node(i, role, ctype, parts, hidden=False):
    return {"id": f"n{i}", "message": {
        "author": {"role": role},
        "content": {"content_type": ctype, "parts": parts},
        "metadata": {"is_visually_hidden_from_conversation": hidden}}}


@pytest.fixture
def chatgpt_html():
    nodes = [
        _node(0, "system", "text", [""], hidden=True),
        _node(1, "user", "text", ["like assume i have 2 tables and both have 10 lakh data"]),
        _node(2, "assistant", "thoughts", ["thinking..."]),
        _node(3, "assistant", "text",
              ["Use a **HashMap** — O(n) instead of O(n²). fileciteturn1file0"]),
        _node(4, "tool", "text", ["The output of this plugin was redacted."]),
        _node(5, "user", "text", ["map.containsKey(103) ---> O(n)?"]),
        _node(6, "assistant", "text",
              ["No — `containsKey` is O(1) on average. fileciteturn5file0L5-L10\n\n```java\nmap.containsKey(103);\n```"]),
    ]
    root = {"loaderData": {
        "root": {"statsig": ("P", 3)},
        "routes/share.$shareId.($action)": {"serverResponse": {"data": {
            "title": "Estimate Join Processing Time", "default_model_slug": "gpt-5-6",
            "create_time": 1790875879.4, "linear_conversation": nodes}}}},
        "actionData": None, "errors": None}
    payload = json.dumps(_encode_turbo_stream(root), ensure_ascii=False) + "\n"
    return ("<html><script>window.__reactRouterContext.streamController.enqueue("
            + json.dumps(payload) + ");</script></html>")


@pytest.fixture
def claude_json():
    return json.dumps({"uuid": "abc", "snapshot_name": "MCP server for ChatGPT history",
        "chat_messages": [
            {"index": 1, "sender": "assistant", "content": [
                {"type": "thinking", "thinking": "hidden"},
                {"type": "tool_use", "name": "bash", "input": {}},
                {"type": "text", "text": "Yes, I support MCP. In the app they're called connectors."}]},
            {"index": 0, "sender": "human", "content": [{"type": "text", "text": "do you support the mcp server"}],
             "attachments": [{"file_name": "server.py"}]},
            {"index": 2, "sender": "human", "content": [{"type": "text", "text": "build it for claude too"}]},
        ]})


# ---------------------------------------------------------------- ChatGPT

def test_chatgpt_parses_title_and_visible_messages(chatgpt_html):
    chat = parse_share(chatgpt_html)
    assert chat["source"] == "chatgpt"
    assert chat["title"] == "Estimate Join Processing Time"
    assert chat["model"] == "gpt-5-6"
    assert [m["role"] for m in chat["messages"]] == ["user", "assistant", "user", "assistant"]


def test_chatgpt_strips_hidden_reasoning_tools_and_citations(chatgpt_html):
    texts = " ".join(m["text"] for m in parse_share(chatgpt_html)["messages"])
    assert "thinking..." not in texts
    assert "redacted" not in texts
    assert "filecite" not in texts and "" not in texts
    assert "```java" in texts


def test_chatgpt_rejects_page_without_data():
    with pytest.raises(Exception, match="No conversation data"):
        parse_share("<html><body>nothing here</body></html>")


# ---------------------------------------------------------------- Claude

def test_claude_snapshot_order_and_blocks(tmp_path, claude_json):
    f = tmp_path / "claude_snapshot.json"
    f.write_text(claude_json)
    chat = import_source(str(f))
    assert chat["source"] == "claude"
    assert chat["title"] == "MCP server for ChatGPT history"
    assert [m["role"] for m in chat["messages"]] == ["user", "assistant", "user"]
    assert "[attached: server.py]" in chat["messages"][0]["text"]
    assert "hidden" not in chat["messages"][1]["text"]


def test_claude_share_shell_page_gives_clear_error(tmp_path):
    f = tmp_path / "claude_page.html"
    f.write_text('<!doctype html><html><head><meta name="description" '
                 'content="Shared via Claude, an AI assistant from Anthropic"></head></html>')
    with pytest.raises(ImportError_, match="no messages in it"):
        import_source(str(f))


def test_claude_snapshot_url():
    sid = "0d1c2b3a-1111-2222-3333-444455556666"
    assert snapshot_url(f"https://claude.ai/share/{sid}") == (
        f"https://claude.ai/api/chat_snapshots/{sid}?rendering_mode=messages&render_all_tools=true")


# ---------------------------------------------------------------- merge

def test_merge_and_prompt_messages_alternate(tmp_path, chatgpt_html, claude_json):
    (tmp_path / "gpt.html").write_text(chatgpt_html)
    (tmp_path / "claude.json").write_text(claude_json)
    conv = merge([import_source(str(tmp_path / "gpt.html")),
                  import_source(str(tmp_path / "claude.json"))])
    assert [s["source"] for s in conv["sources"]] == ["chatgpt", "claude"]
    pm = to_prompt_messages(conv)
    assert pm[0]["role"] == "user"
    assert all(pm[i]["role"] != pm[i + 1]["role"] for i in range(len(pm) - 1))
    assert any(m["content"].startswith("[ChatGPT]:") for m in pm if m["role"] == "assistant")
