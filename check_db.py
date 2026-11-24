import sqlite3

conn = sqlite3.connect("customers.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT phone, status, sms_status, registered_at
    FROM customers
""").fetchall()

for row in rows:
    print(dict(row))

conn.close()