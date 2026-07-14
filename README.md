# CyberSec Buddy — Telegram Cybersecurity Education Bot

A feature-rich Telegram bot that teaches cybersecurity concepts using the
Google Gemini API (free tier). Includes AI-powered Q&A, interactive quizzes,
vulnerability lookups, news feeds, and more.

## Features

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with bot overview |
| `/help` | Full command reference |
| `/topics` | Interactive topic explorer with inline buttons |
| `/quiz` | Multiple-choice cybersecurity quiz |
| `/score` | View your quiz performance & badge |
| `/tip` | Random cybersecurity tip |
| `/cve <ID>` | Look up a CVE vulnerability (NVD API) |
| `/news` | Latest cybersecurity news headlines |
| `/checklist` | Personal security best-practices checklist |
| `/reset` | Clear conversation history |
| *Any text* | AI-powered cybersecurity Q&A via Gemini |

## Files in this project
- `bot.py` — the bot itself (all features)
- `requirements.txt` — Python packages it needs
- `.env.example` — template for your secret keys
- `.env` — your actual secret keys (never commit this!)
- `.gitignore` — prevents secrets from being committed

---

## STEP 1: Create your Telegram bot

1. Open Telegram and search for **@BotFather**.
2. Send it the message `/newbot`.
3. Give your bot a name (e.g. "CyberSec Buddy") and a username ending in
   `bot` (e.g. `cybersec_buddy_bot`).
4. BotFather will reply with a **token** that looks like:
   `123456789:ABCdefGhIJKlmNoPQRstuVwxYZ`
5. Copy this token somewhere safe — this is your `TELEGRAM_BOT_TOKEN`.

## STEP 2: Get your free Google Gemini API key

1. Go to https://aistudio.google.com/
2. Sign in with a Google account (no credit card needed for the free tier).
3. Click **Get API key** in the sidebar, then **Create API key**.
4. Let it create a new Google Cloud project if prompted.
5. Copy the key — this is your `GEMINI_API_KEY`.
6. This bot uses the `gemini-2.5-flash` model, which is on Google's free
   tier: no cost as long as you stay within the rate limits (requests per
   minute / per day). If you hit a rate limit, the bot will just show a
   friendly "try again in a moment" message — see STEP 5 below for what
   to do if that happens often.
7. Free-tier limits and eligible models can shift over time — check
   https://ai.google.dev/gemini-api/docs/pricing for what's currently
   free, and swap the `GEMINI_MODEL` value in `bot.py` if needed.

## STEP 3: Test it locally (optional but recommended)

You'll need Python 3.10+ installed.

```bash
# 1. Go into the project folder
cd "cyber buddy"

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file from the template
cp .env.example .env          # on Windows: copy .env.example .env
# Then edit .env and paste in your actual keys

# 5. Run the bot
python bot.py
```

Now open Telegram, search for your bot's username, and send `/start`.

## STEP 4: Deploy for free on Render (so it runs 24/7)

1. Create a free account at https://render.com
2. Push this project to a GitHub repository (create a new repo, upload
   these files: `bot.py`, `requirements.txt`, and this README).
   **Do NOT push your `.env` file** — the `.gitignore` will prevent this.
3. In Render, click **New +** → **Background Worker**.
4. Connect your GitHub repo.
5. Configure:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
6. Under **Environment Variables**, add:
   - `TELEGRAM_BOT_TOKEN` = your token from Step 1
   - `GEMINI_API_KEY` = your key from Step 2
7. Click **Create Background Worker**. Render will build and start it.
8. Check the **Logs** tab — you should see `🤖 CyberSec Buddy is starting (polling mode)...`

That's it — your bot is now live 24/7. Message it on Telegram anytime.

> Note: We use "Background Worker" (not "Web Service") because this bot
> uses polling — it doesn't need to receive incoming web requests, so no
> webhook/port setup is needed. This is the simplest option for beginners.

## Feature Details

### 🤖 AI-Powered Q&A
Ask any cybersecurity question in plain text. The bot uses Google Gemini
to provide clear, educational answers. Each chat has its own conversation
memory, so follow-up questions work naturally.

### 📚 Interactive Topics
The `/topics` command shows inline buttons for 10 cybersecurity topics.
Tap any button to get a detailed explanation — no typing needed.

### 🧠 Quizzes
The `/quiz` command presents random multiple-choice questions with inline
answer buttons. You get instant feedback with explanations. Track your
progress with `/score` and earn badges based on your accuracy!

### 🔍 CVE Lookup
Use `/cve CVE-2024-3094` to look up any CVE from the National Vulnerability
Database. Shows severity, CVSS score, description, and a link to the full
report.

### 📰 News Feed
The `/news` command pulls the latest cybersecurity headlines from
The Hacker News RSS feed — always stay informed about current threats.

### 🛡️ Security Checklist
The `/checklist` command displays a comprehensive personal security
checklist covering passwords, devices, network, email, data, and habits.

## Customizing
- Edit `SYSTEM_PROMPT` in `bot.py` to change the bot's tone, scope, or
  add more topics.
- Edit `QUIZ_QUESTIONS` to add your own quiz questions.
- Edit `CYBER_TIPS` to add more tips.
- Edit `TOPIC_DETAILS` to modify topic explanations.
- Edit `SECURITY_CHECKLIST` to customize the checklist.

## Notes on safety & scope
This bot is designed for **educational** content only — explaining
concepts, defenses, and best practices. It's intentionally set up (via
the system prompt) to redirect away from requests for real attack
tooling or step-by-step hacking instructions against real targets, since
that's not something either Gemini or this bot is meant to provide.

## STEP 5: If you hit rate limits
The free tier has request-per-minute and request-per-day caps (exact
numbers can change — check https://ai.google.dev/gemini-api/docs/rate-limits
for current values). If your bot starts showing the "try again in a
moment" error a lot:
- Wait a minute or two between heavy testing bursts.
- Consider switching `GEMINI_MODEL` in `bot.py` to a lighter model like
  `gemini-2.5-flash-lite` (usually has a higher free-tier request cap,
  at a small quality tradeoff).
- If you outgrow the free tier entirely, you can add a payment method
  in AI Studio to move to paid usage — Gemini's paid rates are also
  low relative to other providers.

## Costs
- Telegram Bot API: free, no limits for this kind of use.
- NVD API (CVE lookups): free, no API key required.
- The Hacker News RSS: free, public feed.
- Render Background Worker (free tier): free, though free-tier services
  may spin down after inactivity on some plans — check Render's current
  free-tier terms at https://render.com/pricing.
- Google Gemini API: **free**, as long as you stay within the free
  tier's rate limits. No credit card required to get started. Check
  current limits and eligible models at
  https://ai.google.dev/gemini-api/docs/pricing since Google adjusts
  these periodically.

## Dependencies
- `python-telegram-bot` — Telegram Bot API wrapper
- `google-genai` — Google Gemini API client
- `python-dotenv` — Load environment variables from `.env`
- `aiohttp` — Async HTTP client (CVE lookup, RSS fetch)
- `feedparser` — Parse RSS/Atom feeds (news)
