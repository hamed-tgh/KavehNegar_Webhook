
import os
import re
import sqlite3
import httpx
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException
import uvicorn

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}

# Find .env relative to main.py
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# Kavenegar configuration
API_KEY = os.environ["KAVENEGAR_API_KEY"]
SENDER = os.environ["KAVENEGAR_SENDER"]
RECEIVER = os.environ["KAVENEGAR_RECEIVER"]

# Bale configuration
BALE_LINK = os.environ["BALE_GROUP_LINK"]

# Webhook security
WEBHOOK_TOKEN = os.environ["WEBHOOK_TOKEN"]

# Server configuration
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# Database configuration
DB_PATH = str(BASE_DIR / os.getenv("DB_PATH", "customers.db"))



def connect_db():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                phone TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'active',
                sms_status TEXT NOT NULL DEFAULT 'pending',
                registered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


init_db()


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize_digits(value):
    return str(value).translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    ))


def normalize_phone(value):
    phone = normalize_digits(value)
    phone = re.sub(r"[\s\-()]", "", phone)

    if phone.startswith("+98"):
        phone = "0" + phone[3:]
    elif phone.startswith("0098"):
        phone = "0" + phone[4:]
    elif phone.startswith("98") and len(phone) == 12:
        phone = "0" + phone[2:]

    if not re.fullmatch(r"09\d{9}", phone):
        raise HTTPException(400, "Invalid mobile number")

    return phone


async def send_sms(phone, message):
    url = (
        f"https://api.kavenegar.com/v1/"
        f"{API_KEY}/sms/send.json"
    )

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            url,
            data={
                "receptor": phone,
                "sender": SENDER,
                "message": message
            }
        )
        response.raise_for_status()
        result = response.json()

    if result.get("return", {}).get("status") != 200:
        raise RuntimeError(f"SMS API error: {result}")

    return result


async def get_payload(request):
    data = dict(request.query_params)

    if request.method == "POST":
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            body = await request.json()
            data.update(body)

        elif "form" in content_type:
            form = await request.form()
            data.update(dict(form))

    return data


@app.api_route("/webhook/sms", methods=["GET", "POST"])
async def sms_webhook(request: Request):

    if request.query_params.get("token") != WEBHOOK_TOKEN:
        raise HTTPException(403, "Forbidden")

    payload = await get_payload(request)
    print("========== NEW WEBHOOK ==========", flush=True)
    print("Payload:", payload, flush=True)
    print("Method:", request.method, flush=True)
    print("=================================", flush=True)

    # Adjust these mappings to Kavenegar's actual callback.
    raw_phone = payload.get("from")
    raw_message = payload.get("message")
    recipient_line = payload.get("to")
    message_id = payload.get("messageid")

    if not raw_phone or raw_message is None:
        raise HTTPException(400, "Missing SMS fields")

    # Only accept messages to our intended line when supplied.
    if recipient_line and str(recipient_line) != RECEIVER:
        return {"status": "ignored_line"}

    phone = normalize_phone(raw_phone)
    message = normalize_digits(raw_message).strip()

    with connect_db() as db:
        customer = db.execute(
            "SELECT * FROM customers WHERE phone = ?",
            (phone,)
        ).fetchone()

        if message == "11":
            if customer:
                db.execute("""
                    UPDATE customers
                    SET status = 'unsubscribed', updated_at = ?
                    WHERE phone = ?
                """, (now(), phone))
            else:
                db.execute("""
                    INSERT INTO customers
                    (phone, status, sms_status, registered_at, updated_at)
                    VALUES (?, 'unsubscribed', 'pending', ?, ?)
                """, (phone, now(), now()))

            return {"status": "unsubscribed"}

        if message == "12":
            if customer:
                db.execute("""
                    UPDATE customers
                    SET status = 'active',
                        sms_status = 'pending',
                        updated_at = ?
                    WHERE phone = ?
                """, (now(), phone))
            else:
                db.execute("""
                    INSERT INTO customers
                    (phone, status, sms_status, registered_at, updated_at)
                    VALUES (?, 'active', 'pending', ?, ?)
                """, (phone, now(), now()))

            return {"status": "reactivated"}

        if message != "50":
            return {"status": "ignored"}

        if customer:
            if customer["status"] == "unsubscribed":
                return {"status": "opted_out"}

            if customer["sms_status"] == "sent":
                return {"status": "already_sent"}
        else:
            db.execute("""
                INSERT INTO customers
                (phone, status, sms_status, registered_at, updated_at)
                VALUES (?, 'active', 'pending', ?, ?)
            """, (phone, now(), now()))

    sms_text = (
        "درخواست عضویت شما در گروه صادراتی ثبت شد.\n"
        "لینک عضویت در گروه بله:\n"
        f"{BALE_LINK}\n"
        "لغو 11"
    )
    print(f"[SMS] Attempting to send SMS to {phone}", flush=True)
    try:
        result = await send_sms(phone, sms_text)

        print(
            f"[SMS SUCCESS] Phone: {phone}, "
            f"API Response: {result}",
            flush=True
        )

    except Exception as e:
        print(
            f"[SMS ERROR] Phone: {phone}, "
            f"Error: {type(e).__name__}: {e}",
            flush=True
        )
        raise HTTPException(
            status_code=502,
            detail="SMS sending failed"
        )


    with connect_db() as db:
        db.execute("""
            UPDATE customers
            SET sms_status = 'sent', updated_at = ?
            WHERE phone = ? AND status = 'active'
        """, (now(), phone))

    return {"status": "sent", "phone": phone}


if __name__ == "__main__":
    

    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT
    )