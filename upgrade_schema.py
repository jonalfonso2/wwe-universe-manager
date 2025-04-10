import sqlite3

conn = sqlite3.connect("data/roster.db")
cursor = conn.cursor()

# Add missing columns if they don't exist
try:
    cursor.execute("ALTER TABLE wrestlers ADD COLUMN brand TEXT")
except sqlite3.OperationalError:
    pass  # Column already exists

try:
    cursor.execute("ALTER TABLE wrestlers ADD COLUMN team TEXT")
except sqlite3.OperationalError:
    pass  # Column already exists

conn.commit()
conn.close()

print("Table updated.")
