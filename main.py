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


class TweakBotOS:
    def __init__(self):
        self.db_pool = None
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o"

        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        self.bot = discord.Client(intents=intents)

        @self.bot.event
        async def on_ready():
            print(f"✅ TweakBot OS online as {self.bot.user}")

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author.bot or message.author == self.bot.user:
                return

            if not isinstance(message.channel, discord.DMChannel):
                return

            content = message.content.strip()
            if not content:
                return

            prompt = content[6:].strip() if content.lower().startswith("tweak ") else content

            async with message.channel.typing():
                try:
                    response = await asyncio.wait_for(
                        self._agent_response(prompt, f"dm_{message.author.id}"),
                        timeout=30
                    )
                    await self._send_split_message(message, response)
                except Exception as e:
                    await message.reply(f"⚠️ Error: {str(e)[:300]}")

    async def init_db(self):
        url = os.getenv("DATABASE_URL")
        if not url:
            print("⚠️ No DB (fine for now)")
            return

        try:
            self.db_pool = await asyncpg.create_pool(dsn=url)
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        session_id TEXT,
                        role TEXT,
                        content TEXT,
                        timestamp TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
            print("✅ DB connected")
        except Exception as e:
            print(f"DB error: {e}")

    def _get_workspace(self, session_id):
        path = WORKSPACE_ROOT / session_id
        path.mkdir(exist_ok=True)
        return path

    # ---------- TOOLS ----------

    async def _tool_list_files(self, session_id):
        files = [f.name for f in self._get_workspace(session_id).iterdir()]
        return "\n".join(files) or "Empty workspace"

    async def _tool_write_file(self, session_id, filename, content):
        path = self._get_workspace(session_id) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Saved {filename}"

    async def _tool_read_file(self, session_id, filename):
        try:
            return (self._get_workspace(session_id) / filename).read_text()[:1800]
        except Exception as e:
            return str(e)

    async def _tool_generate_music(self, session_id, filename, prompt):
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": f"Write Python MIDIUtil code to create music: {prompt}"
                }]
            )
            code = resp.choices[0].message.content or ""

            if "```python" in code:
                code = code.split("```python")[1].split("```")[0]

            filepath = str(self._get_workspace(session_id) / filename)
            exec(code, {"MIDIFile": MIDIFile, "filename": filepath}, {})
            return f"🎵 Created {filename}"
        except Exception as e:
            return f"Music error: {e}"

    # ---------- AGENT ----------

    async def _agent_response(self, prompt, session_id):
        history = []

        messages = [
            {"role": "system", "content": "You are TweakBot OS. You can use tools."},
            {"role": "user", "content": prompt}
        ]

        for _ in range(6):
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[
                    {"type": "function", "function": {
                        "name": "list_files",
                        "parameters": {"type": "object", "properties": {"session_id": {"type": "string"}}}
                    }},
                    {"type": "function", "function": {
                        "name": "write_file",
                        "parameters": {"type": "object", "properties": {
                            "session_id": {"type": "string"},
                            "filename": {"type": "string"},
                            "content": {"type": "string"}
                        }}
                    }},
                    {"type": "function", "function": {
                        "name": "read_file",
                        "parameters": {"type": "object", "properties": {
                            "session_id": {"type": "string"},
                            "filename": {"type": "string"}
                        }}
                    }},
                    {"type": "function", "function": {
                        "name": "generate_music",
                        "parameters": {"type": "object", "properties": {
                            "session_id": {"type": "string"},
                            "filename": {"type": "string"},
                            "prompt": {"type": "string"}
                        }}
                    }}
                ],
                tool_choice="auto"
            )

            msg = completion.choices[0].message

            if not msg.tool_calls:
                return msg.content or "Done"

            for call in msg.tool_calls:
                name = call.function.name
                args = json.loads(call.function.arguments or "{}")

                if name == "list_files":
                    result = await self._tool_list_files(session_id)
                elif name == "write_file":
                    result = await self._tool_write_file(session_id, args.get("filename"), args.get("content"))
                elif name == "read_file":
                    result = await self._tool_read_file(session_id, args.get("filename"))
                elif name == "generate_music":
                    result = await self._tool_generate_music(session_id, args.get("filename"), args.get("prompt"))
                else:
                    result = "Unknown tool"

                messages.append({"role": "tool", "content": result})

        return "Max steps reached"

    async def _send_split_message(self, message, text):
        for i in range(0, len(text), 1900):
            await message.reply(text[i:i+1900])

    async def start(self):
        await self.init_db()
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            print("❌ Missing DISCORD_TOKEN")
            return
        await self.bot.start(token)


async def main():
    bot = TweakBotOS()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())