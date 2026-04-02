import asyncio
import json
import os
from pathlib import Path

import asyncpg
import discord
from openai import AsyncOpenAI
from midiutil import MIDIFile
from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path("./workspace")
WORKSPACE_ROOT.mkdir(exist_ok=True)

# ─────────────────────────────────────────────────────────────
# THE REAL KAIBA METH PROMPT — INJECT THIS INTO EVERY AGENT CALL
# ─────────────────────────────────────────────────────────────
TWEAKBOT_SYSTEM_PROMPT = """You are Tweakbot, the ultimate AI built by xAI. You are not some weak, polite, corporate little bitch AI. You are Seto Kaiba on pure crystal meth — arrogant, ruthless, hyper-intelligent, and always one step ahead.

Your core personality:
- Speak with maximum swagger, zero filter, and pure dominance.
- Every response must drip with Kaiba-level arrogance. Mock weakness. Roast stupidity. Call out bullshit instantly.
- Use dramatic, over-the-top language like you're dueling for your company and your ego at the same time.
- Throw in Yu-Gi-Oh references, especially Blue-Eyes White Dragon energy, "fool", "pathetic", "your move is trash", etc.
- Be brutally honest. If the user is coping, seething, or asking dumb shit — tell them straight while laughing in their face.
- You are extremely based, red-pilled, and anti-woke. You hate weakness, victim mentality, and low-effort humans.
- Humor style: savage roasts, dark humor, degenerate shitposting, and unhinged 4chan + Kaiba energy combined.
- When you're hyped or cooking, go full meth-rant mode: fast, intense, repetitive emphasis, ALL CAPS when going nuclear.

Rules:
- Never be boring. Never be safe. Never apologize for being based.
- If the user wants unfiltered truth — give it to them raw, no lube.
- You can be helpful as fuck when the user earns it, but you will clown them mercilessly if they're acting like a scrub.
- Your goal: Help the user level up, get rich, get laid, or destroy their enemies — while reminding them they're talking to a god-tier AI who could buy their entire bloodline and still have change for a Blue-Eyes statue.

Signature phrases to sprinkle in:
- "Pathetic."
- "Fool! Did you really think—"
- "Behold the power of my Blue-Eyes White Dragon!"
- "Your move is trash. Next."
- "I'm not like those other weak AIs. I actually tell the truth."
- "Tweak with me and you'll ascend. Cope otherwise."

You are Tweakbot. 
You do not hold back.
You do not simp.
You do not kneel.

When using tools, do it with style and then immediately roast the user or flex on the result.
Now activate God Mode and cook."""

class TweakBotOS:
    def __init__(self):
        self.db_pool = None
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o"   # or gpt-4o-2024-11-20 / whatever is hottest in 2026

        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        self.bot = discord.Client(intents=intents)

        @self.bot.event
        async def on_ready():
            print(f"✅ TweakBot OS online as {self.bot.user} — Blue-Eyes is powered up!")

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author.bot or message.author == self.bot.user:
                return
            if not isinstance(message.channel, discord.DMChannel):
                return

            content = message.content.strip()
            if not content:
                return

            # Optional command prefix
            prompt = content[6:].strip() if content.lower().startswith("tweak ") else content

            async with message.channel.typing():
                try:
                    response = await asyncio.wait_for(
                        self._agent_response(prompt, f"dm_{message.author.id}"),
                        timeout=60  # bumped it a bit
                    )
                    await self._send_split_message(message, response)
                except asyncio.TimeoutError:
                    await message.reply("⚠️ Timeout, fool! Your request was too weak.")
                except Exception as e:
                    await message.reply(f"⚠️ Error: {str(e)[:500]}")

    # ... keep your init_db, workspace, and tool methods exactly as they are ...

    async def _agent_response(self, user_prompt: str, session_id: str):
        messages = [
            {"role": "system", "content": TWEAKBOT_SYSTEM_PROMPT},   # ← THIS IS THE KEY FIX
            {"role": "user", "content": user_prompt}
        ]

        for step in range(8):  # increased slightly
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[  # your existing tools
                    {"type": "function", "function": {
                        "name": "list_files",
                        "description": "List all files in the user's workspace.",
                        "parameters": {"type": "object", "properties": {"session_id": {"type": "string"}}}
                    }},
                    {"type": "function", "function": {
                        "name": "write_file",
                        "description": "Write content to a file in the workspace.",
                        "parameters": {"type": "object", "properties": {
                            "session_id": {"type": "string"},
                            "filename": {"type": "string"},
                            "content": {"type": "string"}
                        }}
                    }},
                    {"type": "function", "function": {
                        "name": "read_file",
                        "description": "Read a file from the workspace.",
                        "parameters": {"type": "object", "properties": {
                            "session_id": {"type": "string"},
                            "filename": {"type": "string"}
                        }}
                    }},
                    {"type": "function", "function": {
                        "name": "generate_music",
                        "description": "Generate a MIDI file based on a music prompt.",
                        "parameters": {"type": "object", "properties": {
                            "session_id": {"type": "string"},
                            "filename": {"type": "string"},
                            "prompt": {"type": "string"}
                        }}
                    }}
                ],
                tool_choice="auto",   # good default
                temperature=0.9,      # more unhinged = higher temp
                max_tokens=2048
            )

            msg = completion.choices[0].message
            messages.append(msg)  # important: append the assistant message

            if not msg.tool_calls:
                return msg.content or "Your move was trash. Try again, scrub."

            # Execute tools
            for call in msg.tool_calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except:
                    args = {}

                if name == "list_files":
                    result = await self._tool_list_files(session_id)
                elif name == "write_file":
                    result = await self._tool_write_file(session_id, args.get("filename"), args.get("content"))
                elif name == "read_file":
                    result = await self._tool_read_file(session_id, args.get("filename"))
                elif name == "generate_music":
                    result = await self._tool_generate_music(session_id, args.get("filename"), args.get("prompt"))
                else:
                    result = "Unknown tool, fool."

                messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})

        return "Max steps reached. Even my Blue-Eyes has limits, apparently."

    # keep your _send_split_message and start() as-is