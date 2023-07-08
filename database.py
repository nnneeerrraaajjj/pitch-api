import sqlite3

# Create the database connection
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Create the "client_info" table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS client_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vertical TEXT NOT NULL,
        self INTEGER DEFAULT 0,
        spouse INTEGER DEFAULT 0,
        children INTEGER DEFAULT 0,
        parent_id INTEGER DEFAULT 0,
        oldest_parent_age INTEGER,
        oldest_children_age INTEGER
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS client_report (
        client_id INTEGER NOT NULL,
        report TEXT,
        FOREIGN KEY (client_id) REFERENCES client_info (id)
    )
''')
conn.commit()


# Helper function to execute raw SQL queries
def execute_query(query, parameters=None):
    if parameters:
        cursor.execute(query, parameters)
    else:
        cursor.execute(query)
    conn.commit()
    return cursor.fetchall()