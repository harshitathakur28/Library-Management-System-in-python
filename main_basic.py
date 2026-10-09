"""
main.py
Library Management System - Modern GUI (Tkinter + ttkbootstrap + SQLite)

Features:
    - Admin login
    - Dashboard with live statistics cards
    - Books tab        : add, update, delete, search, view
    - Members tab      : add, view
    - Issue / Return   : issue a book, return a book, automatic fine
    - Light / Dark theme switch

All database work is done in database.py (imported here as db).
Install the theme library once with:
    python3.11 -m pip install ttkbootstrap
"""

import os
os.environ["TK_SILENCE_DEPRECATION"] = "1"   # hides the macOS Tk warning

import tkinter as tk
from tkinter import messagebox

try:
    import ttkbootstrap as ttk
except ImportError:
    print("ttkbootstrap is not installed.")
    print("Run:  python3.11 -m pip install ttkbootstrap")
    raise SystemExit(1)

import database as db

LIGHT_THEME = "flatly"
DARK_THEME = "darkly"


# ------------------------------------------------------------------ HELPERS
def center_window(win, width, height):
    """Place a window in the middle of the screen."""
    x = (win.winfo_screenwidth() - width) // 2
    y = (win.winfo_screenheight() - height) // 3
    win.geometry(f"{width}x{height}+{x}+{y}")


def apply_table_style(root):
    """Taller rows and bold headings so tables look clean."""
    root.style.configure("Treeview", rowheight=30, font=("Helvetica", 12))
    root.style.configure("Treeview.Heading", font=("Helvetica", 12, "bold"))


def make_table(parent, columns, widths, height=10):
    """
    Create a Treeview table with a scrollbar.
    columns : list of column names
    widths  : list of column widths (same length as columns)
    """
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    table = ttk.Treeview(frame, columns=columns, show="headings",
                         height=height, bootstyle="primary")
    for name, width in zip(columns, widths):
        table.heading(name, text=name)
        table.column(name, width=width,
                     anchor="center" if width <= 100 else "w")

    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    table.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    return table


def fill_table(table, rows):
    """Remove old rows from a table and insert new ones."""
    for item in table.get_children():
        table.delete(item)
    for row in rows:
        table.insert("", tk.END, values=row)


# ------------------------------------------------------------- LOGIN SCREEN
def show_login(root):
    """Show the login screen inside the main window."""
    root.title("Library Management - Login")
    center_window(root, 440, 420)

    page = ttk.Frame(root, padding=40)
    page.pack(fill="both", expand=True)

    ttk.Label(page, text="📚", font=("Helvetica", 48)).pack()
    ttk.Label(page, text="Library Management",
              font=("Helvetica", 22, "bold"),
              bootstyle="primary").pack(pady=(0, 5))
    ttk.Label(page, text="Sign in to continue",
              bootstyle="secondary").pack(pady=(0, 20))

    username = tk.StringVar()
    password = tk.StringVar()

    ttk.Label(page, text="Username").pack(anchor="w")
    user_entry = ttk.Entry(page, textvariable=username, width=32)
    user_entry.pack(pady=(2, 10), fill="x")

    ttk.Label(page, text="Password").pack(anchor="w")
    pass_entry = ttk.Entry(page, textvariable=password, show="*", width=32)
    pass_entry.pack(pady=(2, 20), fill="x")

    def attempt_login(event=None):
        """Check the credentials using the database layer."""
        if not username.get().strip() or not password.get():
            messagebox.showerror("Error", "Enter username and password.")
            return
        if db.check_login(username.get().strip(), password.get()):
            page.destroy()           # remove login screen
            show_dashboard(root)     # show main screen
        else:
            messagebox.showerror("Login failed",
                                 "Wrong username or password.")
            password.set("")

    ttk.Button(page, text="Login", command=attempt_login,
               bootstyle="success", width=20).pack(fill="x", ipady=4)

    user_entry.bind("<Return>", attempt_login)
    pass_entry.bind("<Return>", attempt_login)
    user_entry.focus()


# --------------------------------------------------------------- BOOKS TAB
def build_books_tab(parent, notify):
    """Build the Books tab. Returns a function that reloads its table."""
    title = tk.StringVar()
    author = tk.StringVar()
    qty = tk.StringVar()
    search_text = tk.StringVar()
    selected_id = {"value": None}     # id of the row clicked in the table

    # ---- Form ----
    form = ttk.Labelframe(parent, text=" Book Details ", padding=12)
    form.pack(fill="x", padx=10, pady=10)

    ttk.Label(form, text="Title").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(form, textvariable=title, width=30).grid(row=0, column=1, padx=5)
    ttk.Label(form, text="Author").grid(row=0, column=2, padx=5, pady=5, sticky="w")
    ttk.Entry(form, textvariable=author, width=25).grid(row=0, column=3, padx=5)
    ttk.Label(form, text="Quantity").grid(row=0, column=4, padx=5, pady=5, sticky="w")
    ttk.Entry(form, textvariable=qty, width=8).grid(row=0, column=5, padx=5)

    # ---- Search bar ----
    search_frame = ttk.Frame(parent)
    search_frame.pack(fill="x", padx=10)

    # ---- Table ----
    table = make_table(parent, ("ID", "Title", "Author", "Quantity"),
                       (60, 330, 220, 90))

    def load_table(rows=None):
        """Fill the table. If rows is None, load all books."""
        fill_table(table, db.get_books() if rows is None else rows)

    def clear_fields():
        """Empty the form and forget the selected row."""
        title.set("")
        author.set("")
        qty.set("")
        selected_id["value"] = None
        table.selection_remove(table.selection())

    def read_form():
        """Validate the form. Returns (title, author, quantity) or None."""
        t, a, q = title.get().strip(), author.get().strip(), qty.get().strip()
        if not t or not a or not q:
            messagebox.showerror("Error", "Please fill all fields.")
            return None
        if not q.isdigit():
            messagebox.showerror("Error",
                                 "Quantity must be a whole number (0 or more).")
            return None
        return t, a, int(q)

    def on_row_select(event=None):
        """When a row is clicked, copy its values into the form."""
        selection = table.selection()
        if not selection:
            return
        values = table.item(selection[0], "values")
        selected_id["value"] = int(values[0])
        title.set(values[1])
        author.set(values[2])
        qty.set(values[3])

    def add_book():
        data = read_form()
        if data is None:
            return
        db.add_book(*data)
        load_table()
        clear_fields()
        notify()
        messagebox.showinfo("Success", "Book added.")

    def update_book():
        if selected_id["value"] is None:
            messagebox.showerror("Error", "Click a book in the table first.")
            return
        data = read_form()
        if data is None:
            return
        db.update_book(selected_id["value"], *data)
        load_table()
        clear_fields()
        notify()
        messagebox.showinfo("Success", "Book updated.")

    def delete_book():
        if selected_id["value"] is None:
            messagebox.showerror("Error", "Click a book in the table first.")
            return
        if not messagebox.askyesno("Confirm", "Delete this book?"):
            return
        ok, message = db.delete_book(selected_id["value"])
        if ok:
            load_table()
            clear_fields()
            notify()
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("Cannot delete", message)

    def search_book(event=None):
        keyword = search_text.get().strip()
        if not keyword:
            load_table()
            return
        rows = db.search_books(keyword)
        load_table(rows)
        if not rows:
            messagebox.showinfo("Search", "No matching books found.")

    def show_all():
        search_text.set("")
        load_table()

    # ---- Buttons ----
    ttk.Button(form, text="Add", command=add_book,
               bootstyle="success", width=10).grid(row=1, column=1,
                                                   pady=10, sticky="w")
    ttk.Button(form, text="Update", command=update_book,
               bootstyle="warning", width=10).grid(row=1, column=2, pady=10)
    ttk.Button(form, text="Delete", command=delete_book,
               bootstyle="danger", width=10).grid(row=1, column=3, pady=10)
    ttk.Button(form, text="Clear", command=clear_fields,
               bootstyle="secondary", width=10).grid(row=1, column=4, pady=10)

    ttk.Label(search_frame, text="Search (title or author):").pack(side="left")
    search_entry = ttk.Entry(search_frame, textvariable=search_text, width=30)
    search_entry.pack(side="left", padx=8)
    search_entry.bind("<Return>", search_book)
    ttk.Button(search_frame, text="Search", command=search_book,
               bootstyle="primary").pack(side="left", padx=3)
    ttk.Button(search_frame, text="Show All", command=show_all,
               bootstyle="primary-outline").pack(side="left", padx=3)

    table.bind("<<TreeviewSelect>>", on_row_select)
    load_table()
    return load_table


# ------------------------------------------------------------- MEMBERS TAB
def build_members_tab(parent, notify):
    """Build the Members tab. Returns a function that reloads its table."""
    name = tk.StringVar()
    phone = tk.StringVar()

    # ---- Form ----
    form = ttk.Labelframe(parent, text=" Member Details ", padding=12)
    form.pack(fill="x", padx=10, pady=10)

    ttk.Label(form, text="Name").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(form, textvariable=name, width=30).grid(row=0, column=1, padx=5)
    ttk.Label(form, text="Phone").grid(row=0, column=2, padx=5, pady=5, sticky="w")
    ttk.Entry(form, textvariable=phone, width=20).grid(row=0, column=3, padx=5)

    # ---- Table ----
    table = make_table(parent, ("ID", "Name", "Phone"), (60, 330, 200))

    def load_table():
        fill_table(table, db.get_members())

    def add_member():
        n, p = name.get().strip(), phone.get().strip()
        if not n or not p:
            messagebox.showerror("Error", "Please fill all fields.")
            return
        if not p.isdigit() or len(p) != 10:
            messagebox.showerror("Error",
                                 "Phone number must be exactly 10 digits.")
            return
        db.add_member(n, p)
        name.set("")
        phone.set("")
        load_table()
        notify()
        messagebox.showinfo("Success", "Member added.")

    ttk.Button(form, text="Add Member", command=add_member,
               bootstyle="success").grid(row=0, column=4, padx=15)

    load_table()
    return load_table


# ------------------------------------------------------- ISSUE / RETURN TAB
def build_issue_tab(parent, notify):
    """Build the Issue / Return tab. Returns a function that refreshes it."""
    book_choice = tk.StringVar()
    member_choice = tk.StringVar()
    days_var = tk.StringVar(value="7")        # how many days the book is lent
    fine_var = tk.BooleanVar(value=True)      # charge fine if returned late?

    # ---- Issue section ----
    form = ttk.Labelframe(parent, text=" Issue a Book ", padding=12)
    form.pack(fill="x", padx=10, pady=10)

    ttk.Label(form, text="Book").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    book_box = ttk.Combobox(form, textvariable=book_choice, width=40,
                            state="readonly")
    book_box.grid(row=0, column=1, padx=5)

    ttk.Label(form, text="Member").grid(row=0, column=2, padx=5, pady=5, sticky="w")
    member_box = ttk.Combobox(form, textvariable=member_choice, width=28,
                              state="readonly")
    member_box.grid(row=0, column=3, padx=5)

    ttk.Label(form, text="Days").grid(row=1, column=0, padx=5, pady=10, sticky="w")
    ttk.Spinbox(form, from_=1, to=90, textvariable=days_var,
                width=6).grid(row=1, column=1, padx=5, sticky="w")
    ttk.Checkbutton(form, text="Charge fine if returned late",
                    variable=fine_var,
                    bootstyle="round-toggle").grid(row=1, column=2,
                                                   columnspan=2, sticky="w",
                                                   padx=5)

    # ---- Currently issued table ----
    ttk.Label(parent, text="Currently Issued Books",
              font=("Helvetica", 13, "bold")).pack(anchor="w", padx=12)
    table = make_table(parent,
                       ("Issue ID", "Book", "Member", "Issued", "Days",
                        "Due Date", "Fine?", "Status"),
                       (70, 200, 130, 95, 55, 95, 55, 150), height=7)
    table.tag_configure("overdue", foreground="#dc3545")

    def refresh():
        """Reload dropdowns (only books in stock) and the issued table."""
        books = [f"{b[0]} - {b[1]} (Available: {b[3]})"
                 for b in db.get_books() if b[3] > 0]
        members = [f"{m[0]} - {m[1]}" for m in db.get_members()]
        book_box["values"] = books
        member_box["values"] = members
        book_choice.set("")
        member_choice.set("")
        days_var.set("7")
        fine_var.set(True)
        fill_table(table, db.get_issued_books())
        # show overdue rows in red
        for item in table.get_children():
            if table.item(item, "values")[7].startswith("Overdue"):
                table.item(item, tags=("overdue",))

    def issue_book():
        if not book_choice.get() or not member_choice.get():
            messagebox.showerror("Error", "Select a book and a member.")
            return
        # The text starts with the id, e.g. "3 - Python Basics (...)"
        book_id = int(book_choice.get().split(" - ")[0])
        member_id = int(member_choice.get().split(" - ")[0])
        days = days_var.get().strip()
        if not days.isdigit() or not (1 <= int(days) <= 90):
            messagebox.showerror("Error", "Days must be a number from 1 to 90.")
            return
        ok, message = db.issue_book(book_id, member_id, int(days),
                                    fine_var.get())
        if ok:
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("Cannot issue", message)
        refresh()
        notify()

    def return_book():
        selection = table.selection()
        if not selection:
            messagebox.showerror("Error",
                                 "Click an issued book in the table first.")
            return
        issue_id = int(table.item(selection[0], "values")[0])
        if not messagebox.askyesno("Confirm", "Return this book?"):
            return
        ok, message, fine = db.return_book(issue_id)
        if ok:
            messagebox.showinfo("Returned", message)
        else:
            messagebox.showerror("Error", message)
        refresh()
        notify()

    ttk.Button(form, text="Issue Book", command=issue_book,
               bootstyle="success").grid(row=0, column=4, rowspan=2, padx=15)
    ttk.Button(parent, text="Return Selected Book", command=return_book,
               bootstyle="warning").pack(pady=(0, 10))

    refresh()
    return refresh


# -------------------------------------------------------------- DASHBOARD
def make_stat_card(parent, caption, color):
    """Colored card with a big number. Returns the StringVar for the number."""
    value = tk.StringVar(value="0")
    card = ttk.Frame(parent, bootstyle=color, padding=12)
    ttk.Label(card, textvariable=value, font=("Helvetica", 26, "bold"),
              bootstyle=f"inverse-{color}").pack()
    ttk.Label(card, text=caption, font=("Helvetica", 11),
              bootstyle=f"inverse-{color}").pack()
    return card, value


def show_dashboard(root):
    """Main screen: header, statistic cards and three tabs."""
    root.title("Library Management System")
    center_window(root, 980, 760)

    page = ttk.Frame(root)
    page.pack(fill="both", expand=True)

    # ---- Header with theme switch and logout ----
    header = ttk.Frame(page)
    header.pack(fill="x", padx=15, pady=(12, 5))
    ttk.Label(header, text="📚 Library Management System",
              font=("Helvetica", 20, "bold"),
              bootstyle="primary").pack(side="left")

    def logout():
        if messagebox.askyesno("Logout", "Do you want to log out?"):
            page.destroy()
            show_login(root)

    ttk.Button(header, text="Logout", command=logout,
               bootstyle="danger-outline").pack(side="right")

    theme_button = ttk.Button(header, text="🌙 Dark",
                              bootstyle="secondary-outline")
    theme_button.pack(side="right", padx=8)

    def toggle_theme():
        """Switch between light and dark theme."""
        if root.style.theme.name == LIGHT_THEME:
            root.style.theme_use(DARK_THEME)
            theme_button.configure(text="☀ Light")
        else:
            root.style.theme_use(LIGHT_THEME)
            theme_button.configure(text="🌙 Dark")
        apply_table_style(root)

    theme_button.configure(command=toggle_theme)

    # ---- Statistic cards ----
    cards = ttk.Frame(page)
    cards.pack(fill="x", padx=15, pady=8)

    card1, total_titles = make_stat_card(cards, "Book Titles", "primary")
    card2, total_copies = make_stat_card(cards, "Copies Available", "success")
    card3, total_members = make_stat_card(cards, "Members", "info")
    card4, total_issued = make_stat_card(cards, "Currently Issued", "warning")
    for card in (card1, card2, card3, card4):
        card.pack(side="left", fill="x", expand=True, padx=5)

    def refresh_stats():
        """Recalculate the numbers on the cards."""
        books = db.get_books()
        total_titles.set(str(len(books)))
        total_copies.set(str(sum(b[3] for b in books)))
        total_members.set(str(len(db.get_members())))
        total_issued.set(str(len(db.get_issued_books())))

    # ---- Tabs ----
    notebook = ttk.Notebook(page, bootstyle="primary")
    notebook.pack(fill="both", expand=True, padx=15, pady=(5, 15))

    books_tab = ttk.Frame(notebook)
    members_tab = ttk.Frame(notebook)
    issue_tab = ttk.Frame(notebook)

    notebook.add(books_tab, text="  📖 Books  ")
    notebook.add(members_tab, text="  👤 Members  ")
    notebook.add(issue_tab, text="  🔄 Issue / Return  ")

    refresh_books = build_books_tab(books_tab, refresh_stats)
    refresh_members = build_members_tab(members_tab, refresh_stats)
    refresh_issue = build_issue_tab(issue_tab, refresh_stats)

    def on_tab_change(event=None):
        """Reload data when a tab is opened so every tab is up to date."""
        refresh_books()
        refresh_members()
        refresh_issue()
        refresh_stats()

    notebook.bind("<<NotebookTabChanged>>", on_tab_change)
    refresh_stats()
    apply_table_style(root)


# ------------------------------------------------------------------ START
if __name__ == "__main__":
    app = ttk.Window(themename=LIGHT_THEME)
    apply_table_style(app)
    show_login(app)
    app.mainloop()