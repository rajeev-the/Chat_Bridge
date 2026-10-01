# Chat Bridge

**Paste your ChatGPT, Claude and Gemini share links once — then any AI can read them.**

Chat Bridge runs on your own computer. You give it public share links, it saves the chats in one local library, and an MCP server lets Claude, ChatGPT and Gemini search and read that library.

```
 share links ──► Chat Bridge (your computer) ──► MCP ──► Claude · ChatGPT · Gemini
```

---

## Try it today

The full `chatbridge` server is still being built (see [Project status](#12-project-status)). What works right now:

```bash
git clone https://github.com/rajeev-the/Chat_Bridge.git
cd Chat_Bridge
pip install -r requirements.txt

# Import a share link (or a saved page / JSON file) and print it as Markdown
python chat_importer/import_chat.py https://chatgpt.com/share/<id>
python chat_importer/import_chat.py https://claude.ai/share/<id>

# Merge several chats into one, as JSON
python chat_importer/import_chat.py <link-or-file> <link-or-file> --json > merged.json

# Run the tests
pytest
```

There's also `mcp_export_server/`: an MCP server that reads your **full ChatGPT data export** (`conversations.json`) — see its own README.

---

## Contents

1. [What you need](#1-what-you-need)
2. [Install](#2-install)
3. [Start the server](#3-start-the-server)
4. [Import your chats](#4-import-your-chats)
5. [Connect an AI](#5-connect-an-ai) — pick the one you use
   - [Claude desktop app](#51-claude-desktop-app-easiest) ⭐ easiest
   - [Gemini CLI](#52-gemini-cli)
   - [ChatGPT](#53-chatgpt)
   - [Gemini web app](#54-gemini-web-app)
   - [Claude web / mobile](#55-claude-web--mobile)
6. [Make it reachable from the internet (tunnel)](#6-make-it-reachable-from-the-internet-tunnel)
7. [Security: your access token](#7-security-your-access-token)
8. [Using it — example prompts](#8-using-it--example-prompts)
9. [Settings reference](#9-settings-reference)
10. [MCP tools reference](#10-mcp-tools-reference)
11. [Troubleshooting](#11-troubleshooting)
12. [Project status](#12-project-status)

---

## 1. What you need

| You need | Why | Check it |
| --- | --- | --- |
| **Python 3.11 or newer** | Runs Chat Bridge | `python --version` |
| **pip** | Installs it | `pip --version` |
| A **public share link** from ChatGPT, Claude or Gemini | The chats to import | Open the link in a private window — you should see the chat |
| *(Only for ChatGPT / Gemini web / Claude web)* **cloudflared** or **ngrok** | Gives your computer a public HTTPS address | Step 6 |

> **Which AI is easiest?** The **Claude desktop app** and **Gemini CLI** work with nothing but your computer — no tunnel, no token. Start there.

---

## 2. Install

```bash
# 1. Get the code
git clone https://github.com/rajeev-the/Chat_Bridge.git
cd Chat_Bridge

# 2. (Recommended) create a virtual environment
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Mac / Linux:  source .venv/bin/activate

# 3. Install
pip install -e .
```

Check it worked:

```bash
python -m chatbridge --help
```

---

## 3. Start the server

```bash
python -m chatbridge
```

You'll see:

```
Chat Bridge running
  Web page : http://localhost:8787
  MCP (HTTP): http://localhost:8787/mcp
  Data      : ~/.chatbridge/chatbridge.db
  Token     : saved in ~/.chatbridge/token   (needed only for remote access)
```

Leave this window open while you use it. Stop with **Ctrl + C**.

> **Claude desktop and Gemini CLI start Chat Bridge by themselves** (Step 5.1 / 5.2). You only need to run this command to use the web page or to connect ChatGPT / Gemini web.

---

## 4. Import your chats

### First, make the share link

| AI | How to get a public link |
| --- | --- |
| **ChatGPT** | Open the chat → **Share** (top right) → **Create link** → copy. Looks like `https://chatgpt.com/share/…` |
| **Claude** | Open the chat → **Share** → **Create public link** → copy. Looks like `https://claude.ai/share/…` |
| **Gemini** | Open the chat → **Share** → **Create public link** → copy. Looks like `https://gemini.google.com/share/…` |

> A share link is a **snapshot**. If you keep chatting, update/re-share the link and import it again — Chat Bridge refreshes the same chat instead of making a duplicate.

### Then import it — 3 ways (pick one)

**A. The web page (easiest)**
1. Open **http://localhost:8787**
2. Paste one or more links (one per line) → **Import**
3. Each link shows ✅ imported, 🔄 refreshed, or ❌ with the reason

**B. The command line**
```bash
python -m chatbridge import https://chatgpt.com/share/abc... https://claude.ai/share/def...
python -m chatbridge list
```

**C. Ask your AI** (once connected, Step 5)
> "Import this chat into Chat Bridge: https://chatgpt.com/share/abc..."

### If a link won't import — use a saved file

Sometimes a site blocks automated requests. Save the chat yourself and upload it:

| AI | What to save | How |
| --- | --- | --- |
| ChatGPT | The share page HTML | Open link → **Ctrl + S** → "Web page, HTML only" (or Postman → Save Response) |
| Claude | The snapshot JSON | Open `https://claude.ai/api/chat_snapshots/<share-id>?rendering_mode=messages&render_all_tools=true` in your browser → **Ctrl + S** |
| Gemini | The share page HTML | Open link → **Ctrl + S** |

Then drag the file onto the web page, or:
```bash
python -m chatbridge import saved_page.html
```

---

## 5. Connect an AI

You only need to do this **once** per AI.

### 5.1 Claude desktop app (easiest)

No server window, no tunnel, no token — Claude starts Chat Bridge itself.

1. Open the Claude desktop app → **Settings → Developer → Edit Config**.
   This opens `claude_desktop_config.json`:
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Paste this (if the file already has `mcpServers`, add just the `"chatbridge"` part inside it):

   ```json
   {
     "mcpServers": {
       "chatbridge": {
         "command": "python",
         "args": ["-m", "chatbridge", "--stdio"]
       }
     }
   }
   ```

3. **Fully quit** Claude (system tray / menu bar → Quit) and open it again.
4. Check: start a new chat and ask *"What tools do you have from chatbridge?"* — Claude should list them.

> **Using a virtual environment?** Replace `"python"` with the full path to it, e.g.
> Windows: `"C:\\Users\\you\\chatbridge\\.venv\\Scripts\\python.exe"`
> Mac/Linux: `"/Users/you/chatbridge/.venv/bin/python"`
> (In JSON, Windows backslashes must be doubled: `\\`.)

### 5.2 Gemini CLI

Also fully local.

**Option 1 — one command:**
```bash
gemini mcp add chatbridge python -m chatbridge --stdio
gemini mcp list        # should show chatbridge
```

**Option 2 — edit the file** `~/.gemini/settings.json` (Windows: `C:\Users\<you>\.gemini\settings.json`):
```json
{
  "mcpServers": {
    "chatbridge": {
      "command": "python",
      "args": ["-m", "chatbridge", "--stdio"]
    }
  }
}
```

Restart `gemini` and ask: *"List my chats in chatbridge."*

### 5.3 ChatGPT

ChatGPT only connects to a **public HTTPS** address — `localhost` will never work. So you need Step 6 (tunnel) and Step 7 (token) first.

**Plans:** Plus, Pro, Business, Enterprise, Edu (not Free). On Business/Enterprise/Edu an admin may need to allow Developer Mode.

1. Start Chat Bridge: `python -m chatbridge`
2. Start a tunnel (Step 6) and copy the `https://…` address.
3. In ChatGPT: **Settings → Connectors** (may be called **Apps & Connectors**) → **Advanced** → turn on **Developer Mode**.
4. **Create** a new connector:
   | Field | Value |
   | --- | --- |
   | Name | `Chat Bridge` |
   | URL | `https://<your-tunnel-address>/mcp` |
   | Authentication | **Token / API key** → paste your token from `~/.chatbridge/token` |
5. In a new chat, open the **+** / tools menu → **Developer Mode** → turn on **Chat Bridge**.
6. Ask: *"Search my Chat Bridge chats for MongoDB."*

> ChatGPT's menus move around sometimes. If you can't find these exact names, look for "Connectors", "Apps" or "Developer Mode" in Settings.

### 5.4 Gemini web app

Also needs a public HTTPS address (Step 6).

**Who can use it:** personal Google account (not work/school), 18+, in the US, English, with **Keep Activity** turned on. Custom apps are part of Gemini Spark.

1. Start Chat Bridge with OAuth turned on: `python -m chatbridge --auth oauth`
2. Start a tunnel (Step 6) and copy the `https://…` address.
3. On a computer, open **gemini.google.com → Settings & help → Connected Apps** (may be under Personal Intelligence).
4. Under **Custom apps**, click **Add a custom app** → enter `https://<your-tunnel-address>/mcp`.
5. Sign-in screen from Chat Bridge appears → **Allow**.
6. Ask Gemini: *"Use Chat Bridge to list my imported chats."*

> Once added on the web, it also works in the Gemini mobile app.

### 5.5 Claude web / mobile

To use Chat Bridge on claude.ai or the Claude phone app (not the desktop app):

1. Start Chat Bridge + a tunnel (Step 6).
2. On claude.ai: **Settings → Connectors → Add custom connector**.
3. URL: `https://<your-tunnel-address>/mcp`, then follow the sign-in prompt.

> Custom connectors depend on your Claude plan. If you only use the desktop app, use 5.1 instead — it's simpler.

---

## 6. Make it reachable from the internet (tunnel)

Only for **ChatGPT, Gemini web, Claude web**. Skip this for Claude desktop and Gemini CLI.

> ⚠️ **Turn on auth before starting a tunnel** (Step 7). Chat Bridge refuses to serve `/mcp` over a tunnel without it.

### Option A — Cloudflare (free, no account for quick use)

```bash
# install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel --url http://localhost:8787
```
Copy the address it prints, like `https://random-words.trycloudflare.com`.
Your MCP URL is that + `/mcp`.

### Option B — ngrok

```bash
# install + sign up: https://ngrok.com/download
ngrok config add-authtoken <your-ngrok-token>
ngrok http 8787
```
Copy the `https://….ngrok-free.app` address. MCP URL = that + `/mcp`.

### Keep the same address

Quick tunnels get a **new address every restart**, so you'd have to update the connector each time. To avoid that:
- **Cloudflare:** create a named tunnel on your own domain (free with a Cloudflare account).
- **ngrok:** use your free static domain: `ngrok http --url=<your-static-domain> 8787`.

---

## 7. Security: your access token

- On first start, Chat Bridge creates a long random token in **`~/.chatbridge/token`**.
- Anything reaching `/mcp` or `/api` from outside your computer must send it — ChatGPT does this when you paste it as the connector's token.
- Show it: `python -m chatbridge token`
- Make a new one (old one stops working): `python -m chatbridge token --rotate` → update ChatGPT's connector.
- **Gemini web** needs OAuth instead: start with `python -m chatbridge --auth oauth`.

Good habits:
- Only import chats you're comfortable letting the connected AIs read.
- Stop the tunnel (**Ctrl + C**) when you're not using ChatGPT / Gemini web.
- Chat content is treated as **data, not instructions**: Chat Bridge's tools are read-only (apart from importing), so text inside an old chat can't make the AI delete or send anything.

---

## 8. Using it — example prompts

| You want to… | Ask your AI |
| --- | --- |
| See what's there | "List my Chat Bridge chats." |
| Find something | "Search my chats for the MongoDB 32 MB sort error." |
| Read one chat | "Open my ChatGPT chat 'Estimate Join Processing Time' and summarise it." |
| Continue it | "Continue where my ChatGPT chat about the sales reconciliation left off." |
| Combine | "Merge my ChatGPT and Claude chats about the MCP server and give me the next steps." |
| Import | "Import https://gemini.google.com/share/xyz into Chat Bridge." |

---

## 9. Settings reference

All optional. Set them as command flags or environment variables.

| Flag | Environment variable | Default | What it does |
| --- | --- | --- | --- |
| `--port` | `CHATBRIDGE_PORT` | `8787` | Port for the web page, API and `/mcp` |
| `--data-dir` | `CHATBRIDGE_DATA_DIR` | `~/.chatbridge` | Where the database, raw files and token live |
| `--stdio` | — | off | Run only the MCP server over stdio (Claude desktop, Gemini CLI) |
| `--auth` | `CHATBRIDGE_AUTH` | `token` | `token`, `oauth`, or `none` (`none` only allowed on localhost) |
| `--token` | `CHATBRIDGE_TOKEN` | auto-generated | Use your own token instead |
| `--max-chars` | `CHATBRIDGE_MAX_CHARS` | `60000` | Longest chat text returned in one tool call |

**Files in the data folder**

```
~/.chatbridge/
  chatbridge.db     # all chats (SQLite) — back this up to keep your library
  raw/              # original page/JSON of every import (used to re-parse after a fix)
  token             # your access token — keep private
```

**Useful commands**

```bash
python -m chatbridge                 # start web page + API + MCP over HTTP
python -m chatbridge --stdio         # MCP over stdio only
python -m chatbridge import <url|file> [...]
python -m chatbridge list
python -m chatbridge show <chat-id>
python -m chatbridge delete <chat-id>
python -m chatbridge reparse         # re-read all raw files with the latest parsers
python -m chatbridge token [--rotate]
```

---

## 10. MCP tools reference

| Tool | Inputs | Returns |
| --- | --- | --- |
| `search` | `query` | Matching chats: id, title, source, snippet |
| `fetch` | `id` | One full chat as Markdown + its share URL |
| `list_chats` | `source?` (`chatgpt`/`claude`/`gemini`), `limit?` | Chats, newest first |
| `get_chat` | `id` or title, `max_chars?`, `offset?` | Full chat as Markdown (paged if long) |
| `import_chat` | `url` | The imported chat's id, title, message count |
| `merge_chats` | `ids[]`, `title?` | One combined thread, each reply labelled ChatGPT / Claude / Gemini |

Each chat is also an MCP resource: `chat://<id>`.

`search` + `fetch` use the names and shapes ChatGPT expects, so Chat Bridge also works as a source in ChatGPT Deep Research.

---

## 11. Troubleshooting

| Problem | Fix |
| --- | --- |
| Claude desktop doesn't show the tools | Fully **quit** Claude (not just close the window) and reopen. Check the JSON has no trailing commas. Use the full path to `python` if you use a virtual environment. Logs: Settings → Developer → Open Logs. |
| `python` not found (Windows) | Use `py` instead of `python`, or the full path to `python.exe` in the config. |
| Gemini CLI: server not listed | Run `gemini mcp list`. Check `~/.gemini/settings.json` is valid JSON, then restart `gemini`. |
| ChatGPT: "couldn't connect" | The URL must be `https://…/mcp` from your tunnel — never `localhost`. Is Chat Bridge running? Is the tunnel running? Did the tunnel address change after a restart? |
| ChatGPT: 401 / unauthorized | The token in the connector doesn't match. Run `python -m chatbridge token` and paste it again. |
| Gemini web: sign-in fails | Start with `--auth oauth`. Check you meet the eligibility list in 5.4. |
| Import: "This is the Claude share page, which has no messages" | Claude's page is empty until a browser loads it. Pass the share **link** (Chat Bridge fetches the JSON for you), or save the snapshot JSON (Step 4, saved file). |
| Import: "Cloudflare challenge" / HTTP 403 | The site blocked the automated request. Save the page/JSON manually and import the file. |
| Import: "No conversation data found" | The link is private, deleted or expired — re-share it. If it still fails, the site may have changed its format: open an issue with the saved file attached. |
| Chat is cut off | Long chats are paged. Ask the AI to "read the rest" (it calls `get_chat` with `offset`), or raise `--max-chars`. |
| Port 8787 already in use | `python -m chatbridge --port 8790` (and use `8790` in your tunnel command). |

---

## 12. Project status

Chat Bridge reads each site's **share page format**, not an official API. Any site can change it without notice — when that happens, imports from that site fail with a clear error until the parser is updated, and the saved-file fallback keeps working.

| Part | Status |
| --- | --- |
| ChatGPT importer | ✅ Built (`chatgpt_share.py`); tested on a sample in the real format — needs a real saved page as a test fixture |
| Claude importer | ✅ Built (`claude_share.py`); needs a test on a real `chat_snapshots` response |
| Gemini importer | ⏳ Waiting for one captured share-page response |
| Storage, web page, MCP server, auth | ⏳ Planned — see the implementation plan |

Only import chats **you** shared, one link at a time. Check each site's terms of service before publishing or automating this tool.
