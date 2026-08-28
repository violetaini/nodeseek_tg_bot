<div align="center">
  <img src="banner.jpg" alt="NodeSeek Bot Banner" width="150" />
  <h1>NodeSeek Telegram RSS Bot 🚀</h1>
  <p>
    <a href="README.md">English</a> | <a href="README_zh.md">简体中文</a> | <a href="README_zh-TW.md">繁體中文</a> | <a href="README_ja.md">日本語</a>
  </p>
</div>

これは `python-telegram-bot` (v20+) に基づいて開発された完全非同期の Telegram Bot であり、NodeSeek フォーラムの RSS 更新を監視するために特化して設計されています。

**マルチユーザー分離**をサポートしており、各ユーザーが独立して自身の**ブロックキーワード**や**ブロックユーザー**を設定できます。また、**プライベート/パブリックモード**のワンクリック切り替えもサポートしています。

## ✨ 主な機能

- ⚡ **完全非同期アーキテクチャ**: `aiohttp` および `aiosqlite` をベースにしており、リソース消費が極めて低く、高並行処理時でもブロックされません。
- 👥 **マルチユーザー分離**: 各ユーザーが、見たくないキーワードやユーザーをカスタマイズできます。
- 🎛️ **対話型の視覚的メニュー**: インラインキーボード (Inline Keyboard) による純粋なボタン操作。ワンクリックでブロックキーワードの追加や削除が可能です。
- 🔒 **権限管理システム**:
  - **プライベートモード** (デフォルト): 設定された管理者 (`ADMIN_ID`) のみが使用し、プッシュ通知を受け取ることができます。
  - **パブリックモード**: どの Telegram ユーザーでも `/start` でボットを有効にし、バックグラウンドで独立してフィルタリングとプッシュ通知を行えます。

---

## 🛠️ クイックデプロイ

### 1. 環境の準備

サーバーに Python 3.8 以降がインストールされていることを確認してください。

サーバーのターミナルで以下のコマンドを実行し、コードを直接ダウンロードして依存関係をインストールします。

```bash
# ディレクトリの作成と移動
mkdir nodeseek_tg_bot && cd nodeseek_tg_bot

# wget を使用してコアファイルを直接ダウンロード
wget https://raw.githubusercontent.com/violetaini/nodeseek_tg_bot/main/bot.py
wget https://raw.githubusercontent.com/violetaini/nodeseek_tg_bot/main/requirements.txt

# 必要な依存関係をインストール
pip install -r requirements.txt
```
*(Git の使用に慣れている場合は、直接 `git clone https://github.com/violetaini/nodeseek_tg_bot.git` を使用することもできます)*

### 2. Bot の設定

`bot.py` を開き、コード上部の基本設定を変更します。

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"      # Telegram Bot Token に置き換えてください (@BotFather から取得)
ADMIN_ID = 123456789                   # あなたの Telegram ユーザー数字 ID に置き換えてください (@userinfobot から取得)
```

### 3. 実行テスト

コマンドラインで以下を実行します。

```bash
python bot.py
```
`Bot 已上线启动...` (Bot がオンラインになりました) と表示されれば、起動成功です！Telegram でボットに `/start` を送信できます。

---

## 🚀 バックグラウンド常駐実行の推奨 (上級)

ボットをサーバー上で安定して長期間実行させるために、`Systemd` (Linux) または `PM2` を使用して管理することをお勧めします。

### オプション A: Systemd を使用する (Linux ユーザーに推奨)

1. サービスファイルの作成: `sudo nano /etc/systemd/system/nodeseek_bot.service`
2. 以下の内容を入力します (パスは実際のものに変更してください):

```ini
[Unit]
Description=NodeSeek Telegram Bot
After=network.target

[Service]
Type=simple
User=root
# 実際のスクリプトが存在するディレクトリに変更してください
WorkingDirectory=/path/to/nodeseek_tg_bot/
# 実際の Python のパスに変更してください
ExecStart=/usr/bin/python3 /path/to/nodeseek_tg_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. 自動起動の設定とサービスの開始:
```bash
# systemd 設定の再読み込み
sudo systemctl daemon-reload

# ⚠️ 重要なステップ: 自動起動の設定
sudo systemctl enable nodeseek_bot

# サービスの即時開始
sudo systemctl start nodeseek_bot

# 実行ステータスの確認
sudo systemctl status nodeseek_bot
```

### オプション B: PM2 を使用する

```bash
# pm2 をグローバルにインストール (Node.js 環境が必要)
npm install -g pm2

# ボットの起動
pm2 start bot.py --name "nodeseek-bot" --interpreter python3

# 保存して自動起動を設定
pm2 save
pm2 startup
```

## ⚠️ 注意事項

1. **データベースファイル**: ボットの初回実行時、同じディレクトリに自動的に `nodeseek_bot.db` (SQLite データベースファイル) が生成されます。すべてのユーザーのブロックキーワードやデータがここに保存されるため、このファイルを大切に保管してください。
2. **レート制限**: コードには Telegram の `RetryAfter` (429 エラー) のレート制限保護が組み込まれています。ただし、極端なマルチユーザーサブスクリプションモードでは、コマンド `/set_interval 30` または管理パネルを使用して、ポーリング間隔を 10 秒以上に設定することをお勧めします。
