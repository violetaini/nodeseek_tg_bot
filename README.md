<div align="center">
  <img src="banner.jpg" alt="NodeSeek Bot Banner" width="400" />
  <h1>NodeSeek Telegram RSS Bot 🚀</h1>
  <p>
    <a href="README.md">English</a> | <a href="README_zh.md">简体中文</a> | <a href="README_zh-TW.md">繁體中文</a> | <a href="README_ja.md">日本語</a>
  </p>
</div>

A fully asynchronous Telegram bot based on `python-telegram-bot` (v20+), specifically designed for monitoring RSS updates from the NodeSeek forum.

It supports **multi-user isolation**, allowing each user to independently configure their own **blocked keywords** and **blocked authors**. It also features one-click switching between **Private/Public modes**.

## ✨ Core Features

- ⚡ **Fully Asynchronous Architecture**: Built on `aiohttp` and `aiosqlite`. Ultra-low resource footprint and never blocks under high concurrency.
- 👥 **Multi-User Isolation**: Each user can customize the keywords and authors they don't want to see.
- 🎛️ **Interactive Visual Menu**: Pure Inline Keyboard button interaction. Add or delete blocked keywords with a single click.
- 🔒 **Permission Management**:
  - **Private Mode** (Default): Only the configured administrator (`ADMIN_ID`) can use the bot and receive pushes.
  - **Public Mode**: Any Telegram user can enable the bot via `/start`, filtering and pushing independently in the background.

---

## 🛠️ Quick Deployment

### 1. Prerequisites

Ensure Python 3.8+ is installed on your server.

Run the following commands in your server terminal to download the code and install dependencies directly:

```bash
# Create and enter the directory
mkdir nodeseek_tg_bot && cd nodeseek_tg_bot

# Download core files directly using wget
wget https://raw.githubusercontent.com/violetaini/nodeseek_tg_bot/main/bot.py
wget https://raw.githubusercontent.com/violetaini/nodeseek_tg_bot/main/requirements.txt

# Install dependencies
pip install -r requirements.txt
```
*(If you prefer Git, you can simply use `git clone https://github.com/violetaini/nodeseek_tg_bot.git`)*

### 2. Configure Your Bot

Open `bot.py` and modify the basic configuration at the top:

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"      # Replace with your Telegram Bot Token (from @BotFather)
ADMIN_ID = 123456789                   # Replace with your Telegram User Numeric ID (from @userinfobot)
```

### 3. Run a Test

Run it in your terminal:

```bash
python bot.py
```
If you see `Bot 已上线启动...` (Bot is online), it means startup was successful! You can now send `/start` to the bot in Telegram.

---

## 🚀 Background Running Recommendations (Advanced)

To ensure the bot runs stably over the long term on your server, it is recommended to manage it using `Systemd` (Linux) or `PM2`.

### Option A: Using Systemd (Recommended for Linux)

1. Create a service file: `sudo nano /etc/systemd/system/nodeseek_bot.service`
2. Fill in the following content (remember to modify the paths):

```ini
[Unit]
Description=NodeSeek Telegram Bot
After=network.target

[Service]
Type=simple
User=root
# Replace with your actual script directory
WorkingDirectory=/path/to/nodeseek_tg_bot/
# Replace with your actual Python path
ExecStart=/usr/bin/python3 /path/to/nodeseek_tg_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable auto-start on boot and start the service:
```bash
# Reload systemd config
sudo systemctl daemon-reload

# ⚠️ Critical step: Enable auto-start on boot
sudo systemctl enable nodeseek_bot

# Start the service immediately
sudo systemctl start nodeseek_bot

# Check running status
sudo systemctl status nodeseek_bot
```

### Option B: Using PM2

```bash
# Install pm2 globally (requires Node.js environment)
npm install -g pm2

# Start the bot
pm2 start bot.py --name "nodeseek-bot" --interpreter python3

# Save and enable auto-start on boot
pm2 save
pm2 startup
```

## ⚠️ Notes

1. **Database File**: Upon the first run, the bot will automatically generate a `nodeseek_bot.db` (SQLite database file) in the same directory. Please keep this file safe, as all users' blocked keywords and data are stored here.
2. **Rate Limiting**: The code has built-in Telegram `RetryAfter` (Error 429) rate limiting protection. However, in extreme multi-user subscription modes, it is recommended to set the polling interval to over 10 seconds via the `/set_interval` command or the admin panel.
