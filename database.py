"""
database.py
All SQLite code for the Library Management System lives here.
The GUI (main.py) only calls these functions and never writes SQL itself.
"""

import sqlite3
import hashlib
from datetime import datetime, timedelta

DB_NAME = "library.db"
LOAN_DAYS = 7          # days a book can be kept without fine
FINE_PER_DAY = 2       # fine in rupees per extra day
DATE_FORMAT = "%Y-%m-%d"


def get_connection():
    """Open a connection to the database file."""
    return sqlite3.connect(DB_NAME)


def hash_password(password):
    """Return a SHA-256 hash so passwords are not stored as plain text."""
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    """Create all tables (if missing) and add the default admin."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS admin(
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS books(
        book_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        quantity INTEGER NOT NULL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS members(
        member_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS issued_books(
        issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        issue_date TEXT NOT NULL,
        return_date TEXT,
        fine INTEGER DEFAULT 0,
        loan_days INTEGER DEFAULT 7,
        charge_fine INTEGER DEFAULT 1,
        FOREIGN KEY(book_id) REFERENCES books(book_id),
        FOREIGN KEY(member_id) REFERENCES members(member_id))""")

    # Upgrade an older library.db that does not have the new columns yet
    existing = [row[1] for row in cur.execute("PRAGMA table_info(issued_books)")]
    if "loan_days" not in existing:
        cur.execute("ALTER TABLE issued_books ADD COLUMN loan_days INTEGER DEFAULT 7")
    if "charge_fine" not in existing:
        cur.execute("ALTER TABLE issued_books ADD COLUMN charge_fine INTEGER DEFAULT 1")

    # Default admin login: admin / admin123
    cur.execute("INSERT OR IGNORE INTO admin VALUES(?, ?)",
                ("admin", hash_password("admin123")))

    conn.commit()
    conn.close()


# ---------------------------------------------------------------- LOGIN
def check_login(username, password):
    """Return True if username and password are correct."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admin WHERE username=? AND password=?",
                (username, hash_password(password)))
    found = cur.fetchone() is not None
    conn.close()
    return found


# ---------------------------------------------------------------- BOOKS
def add_book(title, author, quantity):
    """Add a new book."""
    conn = get_connection()
    conn.execute("INSERT INTO books(title, author, quantity) VALUES(?,?,?)",
                 (title, author, quantity))
    conn.commit()
    conn.close()


def get_books():
    """Return all books as a list of tuples (id, title, author, quantity)."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM books ORDER BY book_id").fetchall()
    conn.close()
    return rows


def search_books(keyword):
    """Search books by title or author (partial match, not case sensitive)."""
    conn = get_connection()
    like = "%" + keyword + "%"
    rows = conn.execute(
        "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY book_id",
        (like, like)).fetchall()
    conn.close()
    return rows


def update_book(book_id, title, author, quantity):
    """Update an existing book."""
    conn = get_connection()
    conn.execute(
        "UPDATE books SET title=?, author=?, quantity=? WHERE book_id=?",
        (title, author, quantity, book_id))
    conn.commit()
    conn.close()


def delete_book(book_id):
    """
    Delete a book. Returns (True, message) or (False, message).
    A book that is currently issued cannot be deleted.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM issued_books "
                "WHERE book_id=? AND return_date IS NULL", (book_id,))
    if cur.fetchone()[0] > 0:
        conn.close()
        return False, "This book is currently issued and cannot be deleted."
    cur.execute("DELETE FROM books WHERE book_id=?", (book_id,))
    conn.commit()
    conn.close()
    return True, "Book deleted."


# -------------------------------------------------------------- MEMBERS
def add_member(name, phone):
    """Add a new member."""
    conn = get_connection()
    conn.execute("INSERT INTO members(name, phone) VALUES(?,?)", (name, phone))
    conn.commit()
    conn.close()


def get_members():
    """Return all members as (id, name, phone)."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM members ORDER BY member_id").fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------- ISSUE / RETURN
def issue_book(book_id, member_id, loan_days=LOAN_DAYS, charge_fine=True):
    """
    Issue a book to a member for loan_days days.
    If charge_fine is False, no fine is charged even if returned late.
    Returns (True, message) or (False, message).
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT quantity FROM books WHERE book_id=?", (book_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return False, "Book not found."
    if row[0] <= 0:
        conn.close()
        return False, "No copies available."

    now = datetime.now()
    today = now.strftime(DATE_FORMAT)
    due = (now + timedelta(days=loan_days)).strftime(DATE_FORMAT)
    cur.execute("INSERT INTO issued_books"
                "(book_id, member_id, issue_date, loan_days, charge_fine) "
                "VALUES(?,?,?,?,?)",
                (book_id, member_id, today, loan_days, 1 if charge_fine else 0))
    cur.execute("UPDATE books SET quantity = quantity - 1 WHERE book_id=?",
                (book_id,))
    conn.commit()
    conn.close()
    fine_text = "Fine applies if late." if charge_fine else "No fine will be charged."
    return True, f"Book issued on {today} for {loan_days} day(s).\nDue date: {due}\n{fine_text}"


def get_issued_books():
    """
    Return books that are currently issued (not yet returned) as
    (issue_id, book_title, member_name, issue_date, loan_days,
     due_date, fine_option, status)
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT i.issue_id, b.title, m.name, i.issue_date,
               COALESCE(i.loan_days, 7),
               date(i.issue_date, '+' || COALESCE(i.loan_days, 7) || ' days'),
               COALESCE(i.charge_fine, 1)
        FROM issued_books i
        JOIN books b ON b.book_id = i.book_id
        JOIN members m ON m.member_id = i.member_id
        WHERE i.return_date IS NULL
        ORDER BY i.issue_id""").fetchall()
    conn.close()

    today = datetime.now().date()
    result = []
    for issue_id, title, member, issued, days, due, fine_flag in rows:
        late = (today - datetime.strptime(due, DATE_FORMAT).date()).days
        status = f"Overdue by {late} day(s)" if late > 0 else "On time"
        result.append((issue_id, title, member, issued, days, due,
                       "Yes" if fine_flag else "No", status))
    return result


def return_book(issue_id):
    """
    Return an issued book. Calculates fine if kept longer than LOAN_DAYS.
    Returns (True, message, fine) or (False, message, 0).
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT book_id, issue_date, COALESCE(loan_days, 7), "
                "COALESCE(charge_fine, 1) FROM issued_books "
                "WHERE issue_id=? AND return_date IS NULL", (issue_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return False, "Record not found or already returned.", 0

    book_id, issue_date, loan_days, charge_fine = row
    today = datetime.now()
    days_kept = (today - datetime.strptime(issue_date, DATE_FORMAT)).days
    late_days = max(0, days_kept - loan_days)
    fine = late_days * FINE_PER_DAY if charge_fine else 0

    cur.execute("UPDATE issued_books SET return_date=?, fine=? WHERE issue_id=?",
                (today.strftime(DATE_FORMAT), fine, issue_id))
    cur.execute("UPDATE books SET quantity = quantity + 1 WHERE book_id=?",
                (book_id,))
    conn.commit()
    conn.close()

    if fine > 0:
        return True, f"Returned {late_days} day(s) late. Fine: Rs {fine}", fine
    if late_days > 0:
        return True, f"Returned {late_days} day(s) late, but no fine was set for this issue.", 0
    return True, "Book returned on time. No fine.", 0


# ------------------------------------------------------- HISTORY / REPORTS
def get_history():
    """
    Return every issue ever made (returned or not), newest first, as
    (issue_id, book_title, member_name, issue_date, return_date, fine, status)
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT i.issue_id, b.title, m.name, i.issue_date,
               COALESCE(i.return_date, '-'), COALESCE(i.fine, 0),
               CASE WHEN i.return_date IS NULL THEN 'Issued' ELSE 'Returned' END
        FROM issued_books i
        JOIN books b ON b.book_id = i.book_id
        JOIN members m ON m.member_id = i.member_id
        ORDER BY i.issue_id DESC""").fetchall()
    conn.close()
    return rows


def get_top_books(limit=5):
    """Return the most issued books as (title, times_issued)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT b.title, COUNT(*) AS times
        FROM issued_books i JOIN books b ON b.book_id = i.book_id
        GROUP BY b.book_id ORDER BY times DESC, b.title LIMIT ?""",
        (limit,)).fetchall()
    conn.close()
    return rows


def get_total_fine():
    """Return the total fine collected so far (in rupees)."""
    conn = get_connection()
    total = conn.execute(
        "SELECT COALESCE(SUM(fine), 0) FROM issued_books").fetchone()[0]
    conn.close()
    return total


# Create tables automatically whenever this file is imported or run
init_db()


if __name__ == "__main__":
    print("Database ready: library.db created with all tables.")