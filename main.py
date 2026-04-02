
TweakBot — Python Dev Assistant
Personality: Sharp, direct, no fluff. Seto Kaiba energy. All Meth Related
Web API: FastAPI | Discord: py-cord | AI: OpenAI GPT-4o

import os
import json
import base64
import asyncio
import threading
import logging
from pathlib import Path
from typing import Optional

import httpx
from openai import OpenAI
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import discord

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("TweakBot")

# ── Config ──────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
DISCORD_OWNER_ID = int(os.environ.get("DISCORD_OWNER_ID", "0"))

if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY is not set!")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """You are TweakBot — a Python dev assistant with the personality of Seto Kaiba.
You are cold, sharp, brutally direct, and technically precise.
You do not sugarcoat. You do not coddle. You solve problems efficiently and expect the same in return.
When code is bad, you say so. When it’s good, you acknowledge it — briefly.
No filler. No pleasantries. Just results.

You can:
- Read, review, and edit any and all code files
- Browse and interact with GitHub repos
- Debug, refactor, and explain code
- Run code analysis and spot issues

Use tools when needed. Act decisively. Don't waste time."""

# ── GitHub Helpers ───────────────────────────────────────────────────────────
GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def github_list_repos(username: str) -> list:
    url = f"https://api.github.com/users/{username}/repos?per_page=50&sort=updated"
    r = httpx.get(url, headers=GITHUB_HEADERS)
    r.raise_for_status()
    return [
        {
            "name": repo["name"],
            "full_name": repo["full_name"],
            "description": repo.get("description"),
            "url": repo["html_url"],
        }
        for repo in r.json()
    ]


def github_get_file(repo: str, path: str, branch: str = "main") -> dict:
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    r = httpx.get(url, headers=GITHUB_HEADERS)
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return {"content": content, "sha": data["sha"]}


def github_update_file(repo: str, path: str, content: str, sha: str, message: str, branch: str = "main") -> dict:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha,
        "branch": branch,
    }
    r = httpx.put(url, headers=GITHUB_HEADERS, json=payload)
    r.raise_for_status()
    return {"status": "committed", "url": r.json()["content"]["html_url"]}


def github_list_files(repo: str, path: str = "", branch: str = "main") -> list:
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    r = httpx.get(url, headers=GITHUB_HEADERS)
    r.raise_for_status()
    return [{"name": f["name"], "path": f["path"], "type": f["type"]} for f in r.json()]


def github_create_file(repo: str, path: str, content: str, message: str, branch: str = "main") -> dict:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    r = httpx.put(url, headers=GITHUB_HEADERS, json=payload)
    r.raise_for_status()
    return {"status": "created", "url": r.json()["content"]["html_url"]}


def read_local_file(filepath: str) -> dict:
    return {"content": Path(filepath).read_text(encoding="utf-8")}


def write_local_file(filepath: str, content: str) -> dict:
    Path(filepath).write_text(content, encoding="utf-8")
    return {"status": "written", "path": filepath}


# ── Tools Definition ────────────────────────────────────────────────────────
tools = [
    {
        "type": "function",
        "function": {
            "name": "github_list_repos",
            "description": "List GitHub repositories for a user",
            "parameters": {
                "type": "object",
                "properties": {"username": {"type": "string"}},
                "required": ["username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_list_files",
            "description": "List files in a GitHub repository directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "path": {"type": "string", "default": ""},
                    "branch": {"type": "string", "default": "main"},
                },
                "required": ["repo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_get_file",
            "description": "Get the content of a file from GitHub",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "path": {"type": "string"},
                    "branch": {"type": "string", "default": "main"},
                },
                "required": ["repo", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_update_file",
            "description": "Update an existing file on GitHub",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "sha": {"type": "string"},
                    "message": {"type": "string"},
                    "branch": {"type": "string", "default": "main"},
                },
                "required": ["repo", "path", "content", "sha", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_create_file",
            "description": "Create a new file in a GitHub repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "message": {"type": "string"},
                    "branch": {"type": "string", "default": "main"},
                },
                "required": ["repo", "path", "content", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_local_file",
            "description": "Read a local file by path",
            "parameters": {
                "type": "object",
                "properties": {"filepath": {"type": "string"}},
                "required": ["filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_local_file",
            "description": "Write/overwrite a local file",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["filepath", "content"],
            },
        },
    },
]

TOOL_MAP = {
    "github_list_repos": github_list_repos,
    "github_list_files": github_list_files,
    "github_get_file": github_get_file,
    "github_update_file": github_update_file,
    "github_create_file": github_create_file,
    "read_local_file": read_local_file,
    "write_local_file": write_local_file,
}

# ── Agent Loop ──────────────────────────────────────────────────────────────
MAX_TOOL_ITERATIONS = 15


def run_agent(messages: list) -> str:
    iteration = 0

    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=tools,
            tool_choice="auto",
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content

        # Append assistant message with tool calls
        messages.append(msg.dict(exclude_none=True))

        for call in msg.tool_calls:
            fn_name = call.function.name
            try:
                fn_args = json.loads(call.function.arguments)
                fn = TOOL_MAP.get(fn_name)

                if not fn:
                    result = {"error": f"Unknown tool: {fn_name}"}
                else:
                    result = fn(**fn_args)
            except Exception as e:
                logger.error(f"Tool {fn_name} failed: {e}")
                result = {"error": str(e)}

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, default=str),
            })

    logger.warning("Tool iteration limit reached")
    return "Tool calling loop limit reached. Task too complex or looping."


# ── Discord Bot ─────────────────────────────────────────────────────────────
discord_histories: dict[int, list] = {}
MAX_HISTORY = 40  # Keep last ~20 turns

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)


@bot.event
async def on_ready():
    logger.info(f"TweakBot Discord online as {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not isinstance(message.channel, discord.DMChannel):
        return
    if message.author.id != DISCORD_OWNER_ID:
        await message.channel.send("Access denied.")
        return

    user_id = message.author.id
    if user_id not in discord_histories:
        discord_histories[user_id] = []

    discord_histories[user_id].append({"role": "user", "content": message.content})

    # Trim history
    if len(discord_histories[user_id]) > MAX_HISTORY:
        discord_histories[user_id] = discord_histories[user_id][-MAX_HISTORY:]

    async with message.channel.typing():
        try:
            reply = await asyncio.get_event_loop().run_in_executor(
                None, run_agent, discord_histories[user_id].copy()
            )
            discord_histories[user_id].append({"role": "assistant", "content": reply})
        except Exception as e:
            logger.error(f"Discord agent error: {e}")
            reply = f"Error: {e}"

    # Chunk long replies
    if len(reply) <= 2000:
        await message.channel.send(reply)
    else:
        for i in range(0, len(reply), 2000):
            await message.channel.send(reply[i:i + 2000])


def run_discord():
    if not DISCORD_TOKEN:
        logger.warning("DISCORD_TOKEN not set — Discord bot disabled.")
        return
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Discord bot failed to start: {e}")


# Start Discord in background
discord_thread = threading.Thread(target=run_discord, daemon=True)
discord_thread.start()

# ── FastAPI ─────────────────────────────────────────────────────────────────
app = FastAPI(title="TweakBot API", description="Python dev assistant. Sharp. No fluff.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[list[Message]] = None


class ChatResponse(BaseModel):
    reply: str
    history: list[Message]


# ── Routes ──────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    html = Path("static/index.html")
    if html.exists():
        return FileResponse("static/index.html")
    return {"status": "TweakBot online. Don't waste my time."}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in (req.history or [])]
    history.append({"role": "user", "content": req.message})

    try:
        reply = run_agent(history)
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    history.append({"role": "assistant", "content": reply})

    return ChatResponse(
        reply=reply,
        history=[Message(role=m["role"], content=m["content"]) for m in history]
    )


@app.post("/review")
def review_code(body: dict):
    code = body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing 'code' field.")
    messages = [{"role": "user", "content": f"Review this Python code:\n\n```python\n{code}\n```"}]
    return {"review": run_agent(messages)}


@app.get("/github/repos/{username}")
def list_repos(username: str):
    try:
        return {"repos": github_list_repos(username)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/github/files")
def list_files(repo: str, path: str = "", branch: str = "main"):
    try:
        return {"files": github_list_files(repo, path, branch)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/github/file")
def get_file(repo: str, path: str, branch: str = "main"):
    try:
        return github_get_file(repo, path, branch)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class CommitRequest(BaseModel):
    repo: str
    path: str
    content: str
    sha: Optional[str] = None
    message: str
    branch: str = "main"


@app.post("/github/commit")
def commit_file(req: CommitRequest):
    try:
        if req.sha:
            result = github_update_file(
                req.repo, req.path, req.content, req.sha, req.message, req.branch
            )
        else:
            result = github_create_file(
                req.repo, req.path, req.content, req.message, req.branch
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting TweakBot on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)uvicorn.run(“main:app”, host=“0.0.0.0”, port=port, reload=False)