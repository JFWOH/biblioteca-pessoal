import sqlite3

def check_fks():
    conn = sqlite3.connect("data/library.db")
    cur = conn.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    
    for t in tables:
        table_name = t[0]
        fks = cur.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
        for fk in fks:
            # fk = (id, seq, table, from, to, on_update, on_delete, match)
            if fk[2] == 'books':
                print(f"Tabela '{table_name}' referencia 'books' (ON DELETE {fk[6]})")

if __name__ == "__main__":
    check_fks()
