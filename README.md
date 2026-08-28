# NodeSeek Telegram RSS Bot 🚀

这是一个基于 `python-telegram-bot` (v20+) 开发的纯异步 Telegram 机器人，专门用于监控 NodeSeek 论坛的 RSS 更新。

它支持**多用户隔离**，每个用户都可以独立配置自己的**屏蔽词**和**屏蔽作者**。同时支持**私有/公开模式**一键切换。

## ✨ 核心特性

- ⚡ **纯异步架构**：基于 `aiohttp` 和 `aiosqlite`，占用极低，高并发下绝不阻塞。
- 👥 **多用户相互隔离**：每个用户都可以自定义自己不想看到的屏蔽词和讨厌的用户。
- 🎛️ **互动式可视化菜单**：纯 Inline Keyboard 按键交互，添加、删除屏蔽词一键搞定。
- 🔒 **权限管理体系**：
  - **私有模式**（默认）：只允许配置好的管理员（`ADMIN_ID`）使用和接收推送。
  - **公开模式**：任何 Telegram 用户都可以通过 `/start` 启用，并在后台独立过滤和推送。

---

## 🛠️ 快速部署

### 1. 环境准备

确保你已经安装了 Python 3.8+ 版本。

克隆或下载本仓库代码后，安装依赖：

```bash
pip install -r requirements.txt
```

### 2. 配置你的机器人

打开 `bot.py`，在代码顶部修改以下基础配置：

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"      # 替换为你的 Telegram Bot Token（向 @BotFather 申请）
ADMIN_ID = 123456789                   # 替换为你的 Telegram 用户数字 ID（向 @userinfobot 获取）
CHECK_INTERVAL = 30                    # 检查 RSS 的间隔（秒），默认30秒
```

### 3. 运行测试

在命令行中运行：

```bash
python bot.py
```
如果看到 `Bot 已上线启动...`，说明启动成功！你可以去 Telegram 对机器人发送 `/start`。

---

## 🚀 后台常驻运行建议 (进阶)

为了让机器人在服务器上稳定、长期地运行，推荐使用 `Systemd`（Linux）或 `PM2` 进行管理。

### 方案 A：使用 Systemd (推荐 Linux 用户)

1. 创建服务文件：`sudo nano /etc/systemd/system/nodeseek_bot.service`
2. 填入以下内容（注意修改里面的路径）：

```ini
[Unit]
Description=NodeSeek Telegram Bot
After=network.target

[Service]
Type=simple
User=root
# 修改为你实际的脚本所在目录
WorkingDirectory=/path/to/nodeseek_tg_bot/
# 修改为你实际的 Python 路径
ExecStart=/usr/bin/python3 /path/to/nodeseek_tg_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. 设置开机自启并启动服务：
```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# ⚠️ 关键步骤：设置开机自启动
sudo systemctl enable nodeseek_bot

# 立即启动服务
sudo systemctl start nodeseek_bot

# 查看运行状态
sudo systemctl status nodeseek_bot
```

### 方案 B：使用 PM2

```bash
# 全局安装 pm2 (需要 Node.js 环境)
npm install -g pm2

# 启动机器人
pm2 start bot.py --name "nodeseek-bot" --interpreter python3

# 保存并设置开机自启
pm2 save
pm2 startup
```

## ⚠️ 注意事项

1. **数据库文件**：机器人在首次运行时会在同目录下自动生成 `nodeseek_bot.db`（SQLite 数据库文件），请妥善保管该文件，所有用户的屏蔽词和数据均储存在此。
2. **频率限制**：代码内置了 Telegram 的 `RetryAfter` (429 错误) 限速保护，但在极端多人订阅模式下，请不要将 `CHECK_INTERVAL` 设置得过低。
