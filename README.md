Anjir SMS Webhook — Kavenegar + Bale
A Python/FastAPI service that receives SMS commands through a Kavenegar incoming SMS webhook, registers customers in SQLite, and sends a Bale group invitation through the Kavenegar SMS sending API. Includes an Excel export script for the customer list.
> **Project status:** Local/simulated webhook requests have successfully triggered outgoing SMS API calls. Real incoming SMS processing has previously reached the server, but the end-to-end flow following changes to sender/receiver numbers still needs to be confirmed. Kavenegar returning `200` means the *API request was accepted*, **not** that the SMS was delivered.
How it works
```text
Customer sends "50" to incoming number
                  |
                  v
       Kavenegar incoming SMS
                  |
             HTTP POST
                  v
      /webhook/sms (FastAPI)
                  |
          Validate / parse
                  |
          SQLite customers
                  |
      Kavenegar SMS send API
                  |
    Bale invite link + "لغو 11"
```
Important: The webhook is for receiving SMS notifications. Replies are sent using Kavenegar's HTTPS REST API (`/v1/{API_KEY}/sms/send.json`), not through the webhook.
Current SMS numbers
Role	Number
Incoming line (customer sends `50`)	`10001000667777`
Outgoing sender (invitation reply)	`10006003007000`
The outgoing sender must be enabled and authorized for sending in your Kavenegar account.
Expected project files
```text
Anjir webhook/
├── main.py              # FastAPI receiver and SMS workflow
├── .env                 # Local secrets/config (never commit)
├── .gitignore
├── customers.db         # Created by the app
├── export_excel.py      # Customer export utility
├── check_sms.py         # Optional: outgoing SMS delivery status checker
├── test_send_sms.py     # Optional: direct outgoing SMS test
└── README.md
```
File names reflect the scripts used during development; the optional test/check scripts need to exist locally to run their commands.
Prerequisites
Python 3.10+ (recommended)
A Windows Server or another host that can run FastAPI
A Kavenegar account and API key
A receiving SMS line and an authorized outgoing sender
A Bale group invitation link
A publicly reachable HTTPS endpoint for production callbacks
Installation
From PowerShell in the project directory:
```powershell
cd "C:\Users\Administrator\Desktop\Anjir webhook"
python -m pip install fastapi uvicorn httpx python-dotenv python-multipart openpyxl
```
Create a `.env` alongside `main.py`:
```dotenv
# Kavenegar API
KAVENEGAR_API_KEY=REPLACE_WITH_YOUR_NEW_API_KEY

# Incoming SMS number
KAVENEGAR_RECEIVER=10001000667777

# Outgoing SMS sender
KAVENEGAR_SENDER=10006003007000

# Bale group invitation
BALE_GROUP_LINK=https://ble.ir/join/REPLACE_WITH_YOUR_LINK

# Shared callback token (replace with a long random value)
WEBHOOK_TOKEN=REPLACE_WITH_A_RANDOM_SECRET

# FastAPI
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# SQLite
DB_PATH=customers.db
```
> **Security:** API keys and callback tokens were exposed while debugging this project. Rotate them before production. Do not copy old credentials into documentation, screenshots, or a public repository.
In `main.py`, ensure the `.env` is loaded and both phone-line settings are read:
```python
from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

API_KEY = os.environ["KAVENEGAR_API_KEY"]
RECEIVER = os.environ["KAVENEGAR_RECEIVER"]
SENDER = os.environ["KAVENEGAR_SENDER"]
BALE_LINK = os.environ["BALE_GROUP_LINK"]
WEBHOOK_TOKEN = os.environ["WEBHOOK_TOKEN"]
DB_PATH = str(BASE_DIR / os.getenv("DB_PATH", "customers.db"))
```
Start the application
```powershell
python main.py
```
The server should report that Uvicorn is listening on `0.0.0.0:8000`. The `customers` table is created in `customers.db` on startup if it does not already exist. Keep the app running while testing.
To verify the local HTTP server:
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/docs"
```
This checks the FastAPI server, not Kavenegar callback delivery.
Configure the Kavenegar webhook
In the Kavenegar dashboard, configure the incoming SMS callback:
Setting	Value
Method	`POST`
Payload format	`JSON`
Event	Incoming SMS
Callback URL	`https://YOUR_DOMAIN/webhook/sms?token=YOUR_NEW_SECRET`
For temporary HTTP testing only, a reachable public IP and port may be used. Use the actual, verified server IP; a previous troubleshooting session found that the initially configured IP did not match the server's network address. Do not use `localhost` as the callback URL in Kavenegar.
Actual payload observed
The following field names and direction were confirmed in a real incoming callback:
```json
{
  "messageid": 1465233287,
  "from": "09190919752",
  "message": "50",
  "to": "10001000667777"
}
```
`from` — customer mobile number
`to` — your incoming Kavenegar line
`message` — the received command
`messageid` — incoming message ID (lowercase `id`)
In `main.py`, map them like this:
```python
raw_phone = payload.get("from")
raw_message = payload.get("message")
recipient_line = payload.get("to")
message_id = payload.get("messageid")

if recipient_line and str(recipient_line) != RECEIVER:
    return {"status": "ignored_line"}
```
Do not compare `recipient_line` with `SENDER` now that the sending and receiving numbers are different.
SMS commands and database behavior
Incoming message	Intended action
`50`	Register the customer, then request an invitation SMS containing the Bale link
`11`	Mark the customer `unsubscribed` in the local database
`12`	Reactivate the customer in the local database
Anything else	Ignore
The current implementation stores one row per phone number in `customers`, with these columns:
Column	Meaning
`phone`	Unique customer mobile number
`status`	`active` or `unsubscribed`
`sms_status`	Local send state (currently `pending` or `sent`)
`registered_at`	First registration timestamp (UTC)
`updated_at`	Last update timestamp (UTC)
The application checks duplicates: if a customer already has `sms_status = 'sent'`, another `50` is answered with `already_sent` rather than a new SMS. `11` updates the local notification opt-out; it does not remove someone from the Bale group. `12` should only be used for an explicit customer reactivation request.
Known limitation: `sms_status = 'sent'` is currently set after the API accepts a submission, not when the mobile operator confirms delivery. A queued or subsequently cancelled message may therefore appear as `sent` and prevent retries. For production, store outgoing `messageid`, track `queued` / `delivered` / `failed` / `cancelled`, and implement controlled retries with idempotency.
Test the webhook locally (PowerShell)
Windows PowerShell can map `curl` to `Invoke-WebRequest`. This is the recommended native PowerShell test:
```powershell
$body = @{
    from = "09190919752"
    to = "10001000667777"
    message = "50"
    messageid = 999001
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://localhost:8000/webhook/sms?token=YOUR_NEW_SECRET" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```
Use a phone number you control. A successful new request may initiate a real, chargeable SMS.
Common JSON responses:
Response	Meaning
`{"status":"sent", "phone":"..."}`	Kavenegar send request was accepted; delivery is not confirmed
`{"status":"already_sent"}`	Existing record has `sms_status = 'sent'`
`{"status":"opted_out"}`	Customer is unsubscribed
`{"status":"ignored_line"}`	Wrong incoming `to` line, often due to confusing sender and receiver
`{"status":"ignored"}`	Message is not a recognized command
HTTP `400`	Missing/invalid webhook fields
HTTP `403`	Callback token mismatch
HTTP `502`	Kavenegar send request failed
Test an actual incoming SMS
Start `python main.py` and leave the console visible.
Send `50` from a mobile phone to `10001000667777`.
Verify that the FastAPI console shows a new `POST /webhook/sms` request and the parsed payload.
Confirm the customer is stored in the database.
Check whether the outbound API response uses `10006003007000` as `sender`.
Verify the final delivery status of the outgoing message ID. A `200` webhook response or SMS API `status: 1` does not prove delivery.
Send `11` and verify the local customer status becomes `unsubscribed`.
Troubleshooting tip: The Kavenegar callback can return HTTP 200 even when the Python handler returns `ignored_line` or `already_sent`. Log the JSON response status and the decision path, not just the HTTP code. Avoid exposing tokens or full personal data in public logs.
Export registered customers to Excel
```powershell
python export_excel.py
```
Expected output:
```text
Excel exported successfully!
Customers: 1
File: C:\Users\Administrator\Desktop\Anjir webhook\customers_export.xlsx
```
The generated `customers_export.xlsx` includes customer mobile numbers, membership status, SMS state, registration date, and last update. It exports unique database customers, not a full history of every incoming SMS. `Customers: 0` means the current database query returned no customer rows; it does not establish whether Kavenegar received any SMS.
Check outgoing SMS status
Kavenegar's send API provides an outgoing `messageid`. This is different from the incoming webhook's `messageid`.
To check a particular outgoing message, put its ID into `check_sms.py` and run:
```powershell
python check_sms.py
```
Examples previously observed in this project:
`status: 1` — `در صف ارسال` (queued for sending)
`status: 13` — `لغو شده` (cancelled)
The exact reason for cancellation is not explained by status `13` alone. Contact Kavenegar support with the outgoing message ID if it persists, and verify sending permissions for the outgoing line. A local `SMS SUCCESS` log means only that the API accepted the submission.
Troubleshooting
Symptom	What to check
PowerShell `curl -H` fails	Use `Invoke-RestMethod` or explicitly `curl.exe`
Kavenegar webhook test returns `408`	Check correct public IP, firewall/NAT, callback URL, reachability, and response time
Real SMS produces no server log	Check Kavenegar incoming callback configuration and its delivery history

`200 OK`, but customer list is empty	Check whether the handler returned `ignored_line`/`ignored`; inspect real `from`, `to`, `message` fields
`ignored_line`	Compare incoming `to` with `KAVENEGAR_RECEIVER`, not `KAVENEGAR_SENDER`
SMS isn't received by phone	Check outgoing SMS ID's final delivery status; `status: 1` is only queued
`Customers: 0` after deleting database	Restart the app, submit a new valid `50`, and confirm the export script uses the same `DB_PATH`
Repeat tests send no SMS	Existing customer may be marked `sent`; do not reset real opt-outs casually
Security and production readiness
The public FastAPI port was previously scanned with malicious requests. A `404` for those probes is reassuring but does not prove the host is secure.
Before production:
Rotate the Kavenegar API key and callback token; use a long random token and do not commit `.env`.
Serve the public callback over HTTPS, preferably behind a reverse proxy, and restrict direct access to Uvicorn.
Verify callback authenticity where supported (provider signatures, authenticated callbacks, or provider-documented IP allowlists); a URL token alone is insufficient for high-assurance protection.
Avoid logging the callback token, API key, or full customer phone numbers unnecessarily.
Restrict access to `customers.db` and exported Excel files; both contain personal data.
Record incoming `messageid` for deduplication and outgoing `messageid` for status tracking; make retries safe.
Use a durable queue/worker for outgoing SMS so the webhook can acknowledge incoming events quickly without waiting for the SMS API.
Treat unsubscribe commands as authoritative, and do not silently reactivate unsubscribed users during tests.
Back up the SQLite database and run the application under a supervised service, not a manually opened administrator session.
Suggested `.gitignore`:
```gitignore
.env
.venv/
__pycache__/
*.pyc
*.db
*.db-shm
*.db-wal
customers_export.xlsx
```
Current implementation vs. future improvements
The code discussed so far is a small MVP: webhook receiver, SMS command processing, SQLite customer list, outgoing Kavenegar API call, and manual Excel export.
Recommended improvements include a persistent incoming-event log, actual SMS delivery-state tracking, message ID deduplication, an authenticated Excel download endpoint, background SMS dispatch, secure HTTPS deployment, and better monitoring of failed callbacks.
