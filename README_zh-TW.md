<div align="center">
  <img src="banner.jpg" alt="NodeSeek Bot Banner" width="400" />
  <h1>NodeSeek Telegram RSS Bot 🚀</h1>
  <p>
    <a href="README.md">English</a> | <a href="README_zh.md">简体中文</a> | <a href="README_zh-TW.md">繁體中文</a> | <a href="README_ja.md">日本語</a>
  </p>
</div>

這是一個基於 `python-telegram-bot` (v20+) 開發的純異步 Telegram 機器人，專門用於監控 NodeSeek 論壇的 RSS 更新。

它支援**多用戶隔離**，每個用戶都可以獨立配置自己的**屏蔽詞**和**屏蔽作者**。同時支援**私有/公開模式**一鍵切換。

## ✨ 核心特性

- ⚡ **純異步架構**：基於 `aiohttp` 和 `aiosqlite`，佔用極低，高併發下絕不阻塞。
- 👥 **多用戶相互隔離**：每個用戶都可以自定義自己不想看到的屏蔽詞和討厭的用戶。
- 🎛️ **互動式視覺化選單**：純 Inline Keyboard 按鍵互動，添加、刪除屏蔽詞一鍵搞定。
- 🔒 **權限管理體系**：
  - **私有模式**（預設）：只允許配置好的管理員（`ADMIN_ID`）使用和接收推播。
  - **公開模式**：任何 Telegram 用戶都可以透過 `/start` 啟用，並在後台獨立過濾和推播。

---

## 🛠️ 快速部署

### 1. 環境準備

確保你的伺服器已經安裝了 Python 3.8+ 版本。

在伺服器終端運行以下命令，直接下載程式碼並安裝依賴：

```bash
# 建立並進入目錄
mkdir nodeseek_tg_bot && cd nodeseek_tg_bot

# 使用 wget 直接下載核心檔案
wget https://raw.githubusercontent.com/violetaini/nodeseek_tg_bot/main/bot.py
wget https://raw.githubusercontent.com/violetaini/nodeseek_tg_bot/main/requirements.txt

# 安裝所需依賴
pip install -r requirements.txt
```
*(如果你習慣使用 Git，也可以直接 `git clone https://github.com/violetaini/nodeseek_tg_bot.git`)*

### 2. 配置你的機器人

打開 `bot.py`，在程式碼頂部修改以下基礎配置：

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"      # 替換為你的 Telegram Bot Token（向 @BotFather 申請）
ADMIN_ID = 123456789                   # 替換為你的 Telegram 用戶數字 ID（向 @userinfobot 獲取）
```

### 3. 運行測試

在命令列中運行：

```bash
python bot.py
```
如果看到 `Bot 已上线启动...`，說明啟動成功！你可以去 Telegram 對機器人發送 `/start`。

---

## 🚀 後台常駐運行建議 (進階)

為了讓機器人在伺服器上穩定、長期地運行，推薦使用 `Systemd`（Linux）或 `PM2` 進行管理。

### 方案 A：使用 Systemd (推薦 Linux 用戶)

1. 建立服務檔案：`sudo nano /etc/systemd/system/nodeseek_bot.service`
2. 填入以下內容（注意修改裡面的路徑）：

```ini
[Unit]
Description=NodeSeek Telegram Bot
After=network.target

[Service]
Type=simple
User=root
# 修改為你實際的腳本所在目錄
WorkingDirectory=/path/to/nodeseek_tg_bot/
# 修改為你實際的 Python 路徑
ExecStart=/usr/bin/python3 /path/to/nodeseek_tg_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. 設置開機自啟並啟動服務：
```bash
# 重新載入 systemd 配置
sudo systemctl daemon-reload

# ⚠️ 關鍵步驟：設置開機自啟動
sudo systemctl enable nodeseek_bot

# 立即啟動服務
sudo systemctl start nodeseek_bot

# 查看運行狀態
sudo systemctl status nodeseek_bot
```

### 方案 B：使用 PM2

```bash
# 全域安裝 pm2 (需要 Node.js 環境)
npm install -g pm2

# 啟動機器人
pm2 start bot.py --name "nodeseek-bot" --interpreter python3

# 保存並設置開機自啟
pm2 save
pm2 startup
```

## ⚠️ 注意事項

1. **資料庫檔案**：機器人在首次運行時會在同目錄下自動生成 `nodeseek_bot.db`（SQLite 資料庫檔案），請妥善保管該檔案，所有用戶的屏蔽詞和資料均儲存在此。
2. **頻率限制**：程式碼內建了 Telegram 的 `RetryAfter` (429 錯誤) 限速保護，但在極端多人訂閱模式下，建議在後台透過指令 `/set_interval 30` 或管理員選單將輪詢間隔設置在 10 秒以上。
