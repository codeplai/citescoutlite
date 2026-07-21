import sqlite3

try:
    with sqlite3.connect("agroscout.db") as conn:
        conn.execute("DELETE FROM cache_llm;")
        print("Cache cleared")
except Exception as e:
    print(e)
