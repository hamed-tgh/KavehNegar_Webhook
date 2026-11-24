
import os
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

API_KEY = os.environ["KAVENEGAR_API_KEY"]
SENDER = os.environ["KAVENEGAR_SENDER"]

url = f"https://api.kavenegar.com/v1/{API_KEY}/sms/send.json"

response = httpx.post(
    url,
    data={
        "receptor": "09190919752",
        "sender": SENDER,
        "message": "Test SMS"
    },
    timeout=15
)

print(response.json())
