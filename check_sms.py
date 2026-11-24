
import os
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

API_KEY = os.environ["KAVENEGAR_API_KEY"]

# Outgoing SMS message ID, not the incoming webhook ID
MESSAGE_ID = "1463897733"

url = (
    f"https://api.kavenegar.com/v1/"
    f"{API_KEY}/sms/status.json"
)

try:
    response = httpx.post(
        url,
        data={"messageid": MESSAGE_ID},
        timeout=15
    )
    response.raise_for_status()

    result = response.json()

    print("Kavenegar response:")
    print(result)

    for entry in result.get("entries", []):
        print("Message ID:", entry.get("messageid"))
        print("Status:", entry.get("status"))
        print("Description:", entry.get("statustext"))

except Exception as error:
    print("Error:", type(error).__name__, str(error))
