# Crypto Pump Monitor


A Telegram bot that watches Binance and Bybit market data in real time and notifies users when a trading pair moves beyond their selected thresholds.


I built this project to practice asynchronous Python, WebSocket streams and per-user notification settings. It is a monitoring tool, not an automated trading system and not financial advice.


## What it does


- receives live market updates from Binance and Bybit;
- detects rapid price and volume changes;
- lets each Telegram user configure alert thresholds;
- sends formatted signals with exchange and pair information;
- stores user settings and bot state in SQLite;
- supports Docker-based deployment.


## Tech stack


- Python
- aiogram 3
- asyncio and WebSockets
- aiohttp
- aiosqlite
- Docker Compose


## Run locally


```bash
git clone https://github.com/Hackcatimka/crypto-market-alert-bot.git
cd crypto-market-alert-bot
python -m venv .venv
```


Activate the virtual environment, install dependencies and create the local configuration:


```bash
pip install -r requirements.txt
cp .env.example .env
```


Add a Telegram bot token to `.env`, then run:


```bash
python bot.py
```


## Configuration


```env
BOT_TOKEN=your_telegram_bot_token
DB_PATH=bot.db
```


## Status


Portfolio project. Before using it for real market monitoring, add exchange reconnect tests, structured logging and stronger rate-limit handling.


## Disclaimer


This software is provided for educational and monitoring purposes only. It does not execute trades or provide investment recommendations.
