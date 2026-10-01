# ChatGPT History MCP Server

Lets Claude read your exported ChatGPT conversations: list them, open one in full, or search across all of them.

## 1. Export your ChatGPT chats
ChatGPT → **Settings → Data controls → Export data**. Download the zip from the email and unzip it. You need the `conversations.json` file inside.

## 2. Install
Requires Python 3.10+.

```bash
pip install mcp
```

Put `server.py` in a folder, e.g. `C:\mcp\chatgpt` (Windows) or `~/mcp/chatgpt` (Mac/Linux).

## 3. Connect it to the Claude desktop app
Open the Claude desktop app → **Settings → Developer → Edit Config**. This opens `claude_desktop_config.json`. Add:

```json
{
  "mcpServers": {
    "chatgpt-history": {
      "command": "python",
      "args": ["C:\\mcp\\chatgpt\\server.py"],
      "env": {
        "CHATGPT_EXPORT": "C:\\Users\\YOU\\Downloads\\chatgpt-export\\conversations.json"
      }
    }
  }
}
```

On Mac/Linux use `python3` and normal `/` paths. Save, then fully quit and reopen Claude.

## 4. Use it
Just ask Claude things like:
- "List my ChatGPT conversations about Goa"
- "Open my ChatGPT chat 'Trip plan to Goa' and continue from where it left off"
- "Search my ChatGPT history for 'budget'"

## Tools
| Tool | What it does |
|---|---|
| `list_conversations(query, limit)` | Titles, ids and dates, newest first |
| `get_conversation(conversation)` | Full chat by id or title |
| `search_messages(query, limit)` | Matching snippets across all chats |

Everything stays on your computer; the server only reads the file you point it to.
