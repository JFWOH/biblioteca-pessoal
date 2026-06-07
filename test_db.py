import sqlite3

conn = sqlite3.connect('data/library.db')
conn.execute('PRAGMA foreign_keys=ON')
cur = conn.cursor()
cur.execute("INSERT INTO books (title, file_path, file_format) VALUES ('TestBook2', '/fake/path/test2', 'epub')")
book_id = cur.lastrowid
print('inserted book', book_id)

cur.execute("INSERT INTO reading_progress (book_id) VALUES (?)", (book_id,))
print('inserted reading progress')

try:
    cur.execute("DELETE FROM books WHERE id=?", (book_id,))
    conn.commit()
    print('deleted', book_id, 'successfully')
except Exception as e:
    print('Error:', e)
