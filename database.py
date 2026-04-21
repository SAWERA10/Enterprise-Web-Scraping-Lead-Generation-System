import sqlite3

DB_PATH = "output/data.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY,
        name TEXT,
        phone TEXT,
        address TEXT,
        website TEXT
    )
    """)
    conn.close()

def insert_data(data):
    conn = sqlite3.connect(DB_PATH)
    for d in data:
        conn.execute("""
        INSERT INTO businesses(name, phone, address, website)
        VALUES (?, ?, ?, ?)
        """, (d['name'], d['phone'], d['address'], d['website']))
    conn.commit()
    conn.close() 