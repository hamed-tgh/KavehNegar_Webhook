
import os
import sqlite3
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo

# Load .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / os.getenv("DB_PATH", "customers.db")

# Output file
OUTPUT_FILE = BASE_DIR / "customers_export.xlsx"


def export_customers():

    if not DB_PATH.exists():
        print("Database not found:", DB_PATH)
        return

    # Read customers
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        customers = conn.execute("""
            SELECT
                phone,
                status,
                sms_status,
                registered_at,
                updated_at
            FROM customers
            ORDER BY registered_at DESC
        """).fetchall()

    # Create Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Customers"

    headers = [
        "ردیف",
        "شماره موبایل",
        "وضعیت عضویت",
        "وضعیت پیامک",
        "تاریخ ثبت نام",
        "آخرین تغییر"
    ]

    ws.append(headers)

    for index, customer in enumerate(customers, start=1):

        membership_status = {
            "active": "فعال",
            "unsubscribed": "لغو عضویت"
        }.get(customer["status"], customer["status"])

        sms_status = {
            "sent": "ارسال شده",
            "pending": "در انتظار ارسال"
        }.get(customer["sms_status"], customer["sms_status"])

        ws.append([
            index,
            customer["phone"],
            membership_status,
            sms_status,
            customer["registered_at"],
            customer["updated_at"]
        ])

        # Preserve phone number leading zero
        ws.cell(row=index + 1, column=2).number_format = "@"

    # Header formatting
    for cell in ws[1]:
        cell.fill = PatternFill(
            start_color="17365D",
            end_color="17365D",
            fill_type="solid"
        )
        cell.font = Font(
            color="FFFFFF",
            bold=True
        )
        cell.alignment = Alignment(
            horizontal="center"
        )

    # Column widths
    widths = {
        "A": 10,
        "B": 22,
        "C": 20,
        "D": 22,
        "E": 30,
        "F": 30
    }

    for column, width in widths.items():
        ws.column_dimensions[column].width = width

    ws.freeze_panes = "A2"

    # Add filters and formatted table
    if customers:
        table = Table(
            displayName="CustomersTable",
            ref=f"A1:F{len(customers) + 1}"
        )

        style = TableStyleInfo(
            name="TableStyleMedium2",
            showRowStripes=True
        )

        table.tableStyleInfo = style
        ws.add_table(table)
    else:
        ws.auto_filter.ref = "A1:F1"

    wb.save(OUTPUT_FILE)

    print("Excel exported successfully!")
    print("Customers:", len(customers))
    print("File:", OUTPUT_FILE)


if __name__ == "__main__":
    export_customers()
