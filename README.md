# Market Analyzer API

Single-account Telegram capacity aggregator.

## Setup

    sudo apt install -y python3.11 python3.11-venv mongodb-org
    python3.11 -m venv venv
    ./venv/bin/pip install -r requirements.txt
    cp .env.example .env
    ./venv/bin/python -c "from cryptography.fernet import Fernet;print('FERNET_KEY='+Fernet.generate_key().decode())" >> .env
    # fill API_KEY, BOT_TOKEN, ADMIN_IDS

## Run

    ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080
    ./venv/bin/python -m app.admin_bot

Docs: http://127.0.0.1:8080/docs

## Flow

1. `POST /account` with api_id, api_hash, session_string — one account only, replaces any existing one.
2. `POST /sources` for each capacity bot (`start_payload` = `Prices` for TGLion).
3. `POST /scan` — sends `/cap`, falls back to `/capacity`, parses and stores.
4. `GET /prices?country=France`.

No scheduler inside. `PATCH /settings` stores the two check times; your integration calls `/scan`.


Method	Path	Purpose
GET	/account	current account (masked session)
POST	/account	connect / replace the single account
DELETE	/account	disconnect + forget
GET	/sources	list bots
POST	/sources	add bot (start_payload optional)
PATCH	/sources/{id}	edit username / payload / enabled
DELETE	/sources/{id}	remove bot + its prices
POST	/scan	send /cap to every enabled source
GET	/prices?country=	sorted prices
GET/PATCH	/settings	check times + currency
GET	/health	status