# ⚡ Setup Guide

Step-by-step setup for the AI YouTube Shorts pipeline.

## Prerequisites

| #   | Service                       | Link                              | Cost |
| --- | ----------------------------- | --------------------------------- | ---- |
| 1   | Google Account                | https://accounts.google.com       | Free |
| 2   | Google Colab (GPU)            | https://colab.research.google.com | Free |
| 3   | Google AI Studio (Gemini key) | https://aistudio.google.com       | Free |
| 4   | Google Cloud Console          | https://console.cloud.google.com  | Free |
| 5   | YouTube Channel               | https://youtube.com               | Free |
| 6   | Telegram                      | https://telegram.org              | Free |

---

## Step 1 — Google Cloud Project

1. Go to **console.cloud.google.com**
2. Create project: `ai-youtube-automation`
3. Enable APIs: **Google Sheets API**, **Google Drive API**, **YouTube Data API v3**

## Step 2 — Service Account

1. **APIs & Services → Credentials → "+ CREATE CREDENTIALS" → Service account**
2. Name: `sheets-reader`, create key as JSON
3. Rename to `service_account.json`
4. Set `GOOGLE_SERVICE_ACCOUNT_FILE` in `.env`

## Step 3 — Google Sheet

1. Create sheet at https://sheets.new → Name: "AI YouTube Topics"
2. Headers: `Topic | Language | Status | Video URL`
3. Share with your service account email as **Editor**
4. Copy URL → set `GOOGLE_SHEET_URL` in `.env`

## Step 4 — YouTube OAuth2

1. Create OAuth client (Desktop app) in GCP Credentials
2. Run `python get_tokens.py` to obtain refresh token
3. Set `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` in `.env`

## Step 5 — Telegram Bot

1. Message **@BotFather** → `/newbot` → copy token
2. Message **@userinfobot** → copy chat ID
3. Set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` in `.env`

## Step 6 — Avatar Image

Upload a 512×512+ face image → set `AVATAR_IMAGE_PATH` in `.env`

## Step 7 — Run

```bash
cp .env.example .env
# Fill in your values
make install
ai-shorts setup  # Validate config
ai-shorts run    # Run pipeline
```
