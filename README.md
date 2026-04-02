# TweakBot

Python dev assistant. Sharp. Direct. No fluff.

## What it does
- Reviews and edits Python files
- Connects to GitHub — browse repos, read/commit files
- Debugs, refactors, explains code
- Personality: Seto Kaiba. You've been warned.

## Setup

### 1. Clone & install
```bash
git clone <your-repo>
cd tweakbot
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
cp .env.example .env
# Fill in OPENAI_API_KEY and GITHUB_TOKEN
```

Get a GitHub token at: https://github.com/settings/tokens
Scopes needed: `repo` (full repo access)

### 3. Run locally
```bash
python main.py
```

## Deploy on Railway

1. Push this folder to a GitHub repo
2. Create a new Railway project → "Deploy from GitHub repo"
3. Add environment variables in Railway dashboard:
   - `OPENAI_API_KEY`
   - `GITHUB_TOKEN`
4. Railway picks up the `Dockerfile` automatically — done.

## Usage
Just talk to it. Examples:
- `list my repos for username kaiba-dev`
- `read main.py from kaiba-dev/duel-engine`
- `review this code: [paste code]`
- `fix the bug in kaiba-dev/duel-engine src/core.py`
