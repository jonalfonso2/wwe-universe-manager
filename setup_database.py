import sqlite3

# Connect to SQLite database (it will create the file if it doesn't exist)
conn = sqlite3.connect('data/roster.db')
cursor = conn.cursor()

# Create the 'storylines' table
cursor.execute('''CREATE TABLE IF NOT EXISTS storylines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    status TEXT
)''')

# Create the 'storyline_participants' table to link storylines and wrestlers
cursor.execute('''CREATE TABLE IF NOT EXISTS storyline_participants (
    storyline_id INTEGER,
    wrestler_id INTEGER,
    FOREIGN KEY (storyline_id) REFERENCES storylines(id)
    -- You will add a wrestlers table later with wrestler_id and name
)''')

# Create the 'weekly_segments' table for storing events in the storylines
cursor.execute('''CREATE TABLE IF NOT EXISTS weekly_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    storyline_id INTEGER,
    week_number INTEGER,
    event_description TEXT,
    FOREIGN KEY (storyline_id) REFERENCES storylines(id)
)''')
 
cursor.execute('''CREATE TABLE IF NOT EXISTS wrestlers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gender TEXT CHECK(gender IN ('Male', 'Female')) NOT NULL,
    alignment TEXT CHECK(alignment IN ('Heel', 'Face', 'Both')) NOT NULL,
    type TEXT CHECK(type IN ('Striker', 'Technician', 'High Flyer', 'Powerhouse')) NOT NULL
)''')

# Commit and close the connection
conn.commit()
conn.close()

print("Database setup completed.")
