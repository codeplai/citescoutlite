import sqlite3
from adaptadores.autenticacion import Autenticacion

def update_schema():
    auth = Autenticacion()

    with sqlite3.connect("agroscout.db") as conn:
        cur = conn.cursor()

        # 1. Create usuarios table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            org_id INTEGER,
            creado_en TEXT DEFAULT (datetime('now'))
        )
        """)

        # Insert demo users with bcrypt hashed passwords
        admin_hash = auth.hash_password("cite2026")
        demo_gratuita_hash = auth.hash_password("demo2026")
        demo_premium_hash = auth.hash_password("premium2026")

        cur.execute("INSERT OR IGNORE INTO usuarios (email, password_hash, org_id) VALUES (?, ?, ?)",
                    ("admin@cite.gob.pe", admin_hash, 1))
        cur.execute("INSERT OR IGNORE INTO usuarios (email, password_hash, org_id) VALUES (?, ?, ?)",
                    ("demo-gratuita@cite.gob.pe", demo_gratuita_hash, 1))
        cur.execute("INSERT OR IGNORE INTO usuarios (email, password_hash, org_id) VALUES (?, ?, ?)",
                    ("demo-premium@cite.gob.pe", demo_premium_hash, 1))
        
        # 2. Add tokens_entrada and tokens_salida to etapas_ejecucion
        # SQLite doesn't support ADD COLUMN IF NOT EXISTS easily, so we try/except
        try:
            cur.execute("ALTER TABLE etapas_ejecucion ADD COLUMN tokens_entrada INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass # Column likely exists
            
        try:
            cur.execute("ALTER TABLE etapas_ejecucion ADD COLUMN tokens_salida INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass # Column likely exists
            
        conn.commit()
        print("Schema updated successfully.")

if __name__ == "__main__":
    update_schema()
