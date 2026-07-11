import sqlite3
class MemoryManager:
    def __init__(self):
        self.conn = sqlite3.connect('data/roha.db')
        self.cursor = self.conn.cursor()
        self.create_memory_table()

    def create_memory_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL, 
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
        self.conn.commit()

    def store_memory(self, role, content):
        self.cursor.execute('INSERT INTO messages (role, content) VALUES (?, ?)', (role, content))
        self.conn.commit()

    def retrieve_memories(self):
        self.cursor.execute('SELECT content FROM messages')
        return [row[0] for row in self.cursor.fetchall()]

memory = MemoryManager()
