import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "scheduler.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the database, creating the schema if it does not exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Hard Constraints table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS HardConstraints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                day_of_week TEXT NOT NULL, -- 'Monday', 'Tuesday', etc.
                start_time TEXT NOT NULL,  -- 'HH:MM'
                end_time TEXT NOT NULL     -- 'HH:MM'
            )
        """)
        
        # Flexible Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS FlexibleTasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                priority_score INTEGER NOT NULL,
                deadline TEXT,              -- 'YYYY-MM-DD' or None
                completed INTEGER DEFAULT 0 -- 0 = False, 1 = True
            )
        """)
        
        # General Application Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS AppSettings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()

def save_setting(key: str, value: str):
    """Saves or updates a setting in the AppSettings table."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO AppSettings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, str(value)))
        conn.commit()

def get_setting(key: str) -> str:
    """Retrieves a setting value by its key from the AppSettings table. Returns None if not found."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM AppSettings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

def seed_data():
    """Seeds the database with specific test data to verify scheduling logic."""
    # Hard constraints to insert (with day breakdown)
    hard_constraints = [
        # EE 301 Lecture (Mon/Thu 09:30-11:00)
        ("EE 301 Lecture", "Monday", "09:30", "11:00"),
        ("EE 301 Lecture", "Thursday", "09:30", "11:00"),
        
        # EE 302 Lecture (Tue/Fri 14:00-15:30)
        ("EE 302 Lecture", "Tuesday", "14:00", "15:30"),
        ("EE 302 Lecture", "Friday", "14:00", "15:30"),
        
        # Chemistry Club Meeting (Wed 18:00-19:00)
        ("Chemistry Club Meeting", "Wednesday", "18:00", "19:00")
    ]
    
    # Flexible tasks to insert
    flexible_tasks = [
        ("Debug PyTorch Geometric tensor shapes for traffic GNN", 120, 9, None),
        ("Write CUDA kernel for shared memory optimization", 180, 8, None),
        ("Draft ChemETL event email", 30, 4, None)
    ]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Only seed if tables are empty
        cursor.execute("SELECT COUNT(*) FROM HardConstraints")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("""
                INSERT INTO HardConstraints (title, day_of_week, start_time, end_time)
                VALUES (?, ?, ?, ?)
            """, hard_constraints)
            print("Seeded HardConstraints.")
            
        cursor.execute("SELECT COUNT(*) FROM FlexibleTasks")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("""
                INSERT INTO FlexibleTasks (title, duration_minutes, priority_score, deadline)
                VALUES (?, ?, ?, ?)
            """, flexible_tasks)
            print("Seeded FlexibleTasks.")
            
        conn.commit()

def get_hard_constraints(day_of_week: str):
    """Retrieves all hard constraints for a specific day of the week, sorted by start time."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, start_time, end_time 
            FROM HardConstraints 
            WHERE LOWER(day_of_week) = LOWER(?)
            ORDER BY start_time ASC
        """, (day_of_week,))
        return [{"title": r[0], "start_time": r[1], "end_time": r[2]} for r in cursor.fetchall()]

def get_pending_flexible_tasks():
    """Retrieves all incomplete flexible tasks, sorted by priority score (descending)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, duration_minutes, priority_score, deadline 
            FROM FlexibleTasks 
            WHERE completed = 0
            ORDER BY priority_score DESC
        """)
        return [{
            "id": r[0],
            "title": r[1],
            "duration_minutes": r[2],
            "priority_score": r[3],
            "deadline": r[4]
        } for r in cursor.fetchall()]

def insert_flexible_task(title: str, duration_minutes: int, priority_score: int, deadline: str = None):
    """Inserts a new flexible task into the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO FlexibleTasks (title, duration_minutes, priority_score, deadline)
            VALUES (?, ?, ?, ?)
        """, (title, duration_minutes, priority_score, deadline))
        conn.commit()

def complete_flexible_task(task_id: int):
    """Marks a flexible task as completed in the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE FlexibleTasks SET completed = 1 WHERE id = ?", (task_id,))
        conn.commit()

if __name__ == "__main__":
    init_db()
    seed_data()
    print("Database initialization and seeding completed successfully.")
