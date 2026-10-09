"""
main.py
Library Management System - Interactive GUI (Tkinter + ttkbootstrap + SQLite)

Features:
    - Admin login (show/hide password)
    - Dashboard: animated, clickable statistic cards, live clock
    - Books tab        : add, update, delete, live search, sortable table
    - Members tab      : add, live search, copy phone number
    - Issue / Return   : choose days, optional fine, double-click to return
    - History tab      : every issue ever made, with search
    - Reports tab      : usage meter, most-issued chart, fines, CSV export
    - Table hover highlight, striped rows, right-click menus
    - Toast notifications, overdue alert, keyboard shortcuts, theme picker

All database work is done in database.py (imported here as db).
Install the theme library once with:
    python3.11 -m pip install ttkbootstrap
"""

import os
os.environ["TK_SILENCE_DEPRECATION"] = "1"   # hides the macOS Tk warning

import csv
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)  # quiet theme-name notices

try:
    import ttkbootstrap as ttk
except ImportError as error:
    print("Could not load ttkbootstrap:", error)
    print("Run:  python3.11 -m pip install ttkbootstrap")
    raise SystemExit(1)

# ToastNotification lives in different places in different ttkbootstrap
# versions, so try each location. If none works, normal pop-ups are used.
ToastNotification = getattr(ttk, "ToastNotification", None)
if ToastNotification is None:
    for module_name in ("ttkbootstrap.widgets", "ttkbootstrap.toast"):
        try:
            module = __import__(module_name, fromlist=["ToastNotification"])
            ToastNotification = module.ToastNotification
            break
        except (ImportError, AttributeError):
            continue

import database as db

START_THEME = "flatly"
THEMES = ["flatly", "cosmo", "litera", "minty", "journal",
          "darkly", "superhero", "cyborg", "solar"]


# ------------------------------------------------------------------ HELPERS
def center_window(win, width, height):
    """Place a window in the middle of the screen."""
    x = (win.winfo_screenwidth() - width) // 2
    y = (win.winfo_screenheight() - height) // 3
    win.geometry(f"{width}x{height}+{x}+{y}")


def blend(color1, color2, amount):
    """Mix two '#rrggbb' colors. amount=0 gives color1, 1 gives color2."""
    c1 = [int(color1[i:i + 2], 16) for i in (1, 3, 5)]
    c2 = [int(color2[i:i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(a + (b - a) * amount) for a, b in zip(c1, c2)]
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def toast(message, style="success", title="Library"):
    """
    Small pop-up message in the corner that disappears by itself.
    style: success (green), warning (yellow), danger (red), info (blue).
    Falls back to a normal message box if the toast cannot be shown.
    """
    try:
        if ToastNotification is None:
            raise RuntimeError("toast not available")
        ToastNotification(title=title, message=message, duration=3500,
                          bootstyle=style, position=(20, 60, "ne")).show_toast()
    except Exception:
        messagebox.showinfo(title, message)


def apply_table_style(root):
    """Taller rows and bold headings so tables look clean."""
    root.style.configure("Treeview", rowheight=30, font=("Helvetica", 12))
    root.style.configure("Treeview.Heading", font=("Helvetica", 12, "bold"))


def add_hover(table):
    """Highlight the row under the mouse pointer."""
    state = {"item": None, "tags": ()}

    def restore():
        item = state["item"]
        if item and table.exists(item):
            table.item(item, tags=state["tags"])
        state["item"] = None

    def on_motion(event):
        item = table.identify_row(event.y)
        if item == state["item"]:
            return
        restore()
        if item:
            state["item"] = item
            state["tags"] = table.item(item, "tags")
            # hover replaces the stripe color but keeps e.g. the red "overdue"
            keep = [t for t in state["tags"] if t not in ("odd", "even")]
            table.item(item, tags=keep + ["hover"])

    table.bind("<Motion>", on_motion)
    table.bind("<Leave>", lambda e: restore())


def add_context_menu(table, items):
    """Right-click (or Control-click on Mac) menu. items = [(label, command)]"""
    menu = tk.Menu(table, tearoff=0)
    for label, command in items:
        menu.add_command(label=label, command=command)

    def show(event):
        row = table.identify_row(event.y)
        if row:
            table.selection_set(row)
            menu.tk_popup(event.x_root, event.y_root)

    table.bind("<Button-2>", show)
    table.bind("<Button-3>", show)
    table.bind("<Control-Button-1>", show)


def make_table(parent, columns, widths, height=10):
    """
    Create a Treeview table with a scrollbar, hover highlight and
    click-on-heading sorting (click again to reverse).
    """
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    table = ttk.Treeview(frame, columns=columns, show="headings",
                         height=height, bootstyle="primary")
    sort_state = {"col": None, "reverse": False}

    def reset_headings():
        """Remove the sort arrows (used when the table is reloaded)."""
        sort_state["col"] = None
        for name in columns:
            table.heading(name, text=name)

    def sort_by(col):
        """Sort rows by a column. Numbers are sorted as numbers."""
        reverse = (sort_state["col"] == col) and not sort_state["reverse"]

        def key(pair):
            try:
                return (0, float(pair[0]))
            except ValueError:
                return (1, pair[0].lower())

        items = [(table.set(i, col), i) for i in table.get_children("")]
        items.sort(key=key, reverse=reverse)
        for index, (_, item) in enumerate(items):
            table.move(item, "", index)

        sort_state["col"] = col
        sort_state["reverse"] = reverse
        for name in columns:
            arrow = ""
            if name == col:
                arrow = "  ▼" if reverse else "  ▲"
            table.heading(name, text=name + arrow)

    for name, width in zip(columns, widths):
        table.heading(name, text=name, command=lambda c=name: sort_by(c))
        table.column(name, width=width,
                     anchor="center" if width <= 100 else "w")

    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    table.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    table.reset_headings = reset_headings
    add_hover(table)
    return table


def fill_table(table, rows, flag_col=None):
    """
    Replace the rows of a table. Rows get alternating (striped) colors.
    If flag_col is given, rows whose text there starts with 'Overdue'
    are marked red.
    """
    colors = ttk.Style().colors
    base = colors.inputbg
    table.tag_configure("odd", background=base)
    table.tag_configure("even", background=blend(base, colors.fg, 0.07))
    table.tag_configure("hover", background=blend(base, colors.primary, 0.25))
    table.tag_configure("overdue", foreground="#dc3545")

    for item in table.get_children():
        table.delete(item)
    for index, row in enumerate(rows):
        tags = ["even" if index % 2 else "odd"]
        if flag_col is not None and str(row[flag_col]).startswith("Overdue"):
            tags.append("overdue")
        table.insert("", tk.END, values=row, tags=tags)
    table.reset_headings()


def export_csv(default_name, headers, rows):
    """Ask where to save, then write a CSV file."""
    path = filedialog.asksaveasfilename(
        defaultextension=".csv", initialfile=default_name,
        filetypes=[("CSV files", "*.csv")])
    if not path:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    toast(f"Saved {len(rows)} row(s) to {os.path.basename(path)}", "info",
          "Export complete")


# ------------------------------------------------------------- LOGIN SCREEN
def show_login(root):
    """Show the login screen inside the main window."""
    root.title("Library Management - Login")
    center_window(root, 440, 470)

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
    pass_entry.pack(pady=(2, 8), fill="x")

    show_pass = tk.BooleanVar(value=False)

    def toggle_password():
        """Show or hide the typed password."""
        pass_entry.configure(show="" if show_pass.get() else "*")

    ttk.Checkbutton(page, text="Show password", variable=show_pass,
                    command=toggle_password,
                    bootstyle="round-toggle").pack(anchor="w", pady=(0, 15))

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

    user_entry.bind("<Return>", lambda e: pass_entry.focus())  # Enter -> next
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
    title_entry = ttk.Entry(form, textvariable=title, width=30)
    title_entry.grid(row=0, column=1, padx=5)
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
    count_label = ttk.Label(parent, text="", bootstyle="secondary")
    count_label.pack(anchor="w", padx=14, pady=(0, 6))

    def load_table(rows=None):
        """Fill the table. If rows is None, load all books."""
        if rows is None:
            rows = db.get_books()
        fill_table(table, rows)
        count_label.configure(text=f"Showing {len(rows)} book(s)   •   "
                                   "click a column heading to sort")

    def clear_fields():
        """Empty the form and forget the selected row."""
        title.set("")
        author.set("")
        qty.set("")
        selected_id["value"] = None
        table.selection_remove(table.selection())
        title_entry.focus()

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

    def apply_search(*args):
        """Live search: runs every time the search text changes."""
        keyword = search_text.get().strip()
        load_table(db.search_books(keyword) if keyword else None)

    def add_book():
        data = read_form()
        if data is None:
            return
        db.add_book(*data)
        apply_search()
        clear_fields()
        notify()
        toast(f"Book '{data[0]}' added.", "success")

    def update_book():
        if selected_id["value"] is None:
            messagebox.showerror("Error", "Click a book in the table first.")
            return
        data = read_form()
        if data is None:
            return
        db.update_book(selected_id["value"], *data)
        apply_search()
        clear_fields()
        notify()
        toast("Book updated.", "info")

    def delete_book():
        on_row_select()              # make sure the clicked row is selected
        if selected_id["value"] is None:
            messagebox.showerror("Error", "Click a book in the table first.")
            return
        if not messagebox.askyesno("Confirm", "Delete this book?"):
            return
        ok, message = db.delete_book(selected_id["value"])
        if ok:
            apply_search()
            clear_fields()
            notify()
            toast(message, "danger")
        else:
            messagebox.showerror("Cannot delete", message)

    def show_all():
        search_text.set("")          # this also reloads the full table

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

    ttk.Label(search_frame, text="🔍 Search:").pack(side="left")
    ttk.Entry(search_frame, textvariable=search_text,
              width=34).pack(side="left", padx=8)
    ttk.Label(search_frame, text="(type to filter by title or author)",
              bootstyle="secondary").pack(side="left", padx=4)
    ttk.Button(search_frame, text="Show All", command=show_all,
               bootstyle="primary-outline").pack(side="left", padx=6)

    table.bind("<<TreeviewSelect>>", on_row_select)
    add_context_menu(table, [("Delete this book", delete_book)])
    title_entry.bind("<Return>", lambda e: add_book())
    load_table()
    search_text.trace_add("write", apply_search)   # live search starts now
    return apply_search      # reloads the table while keeping the search


# ------------------------------------------------------------- MEMBERS TAB
def build_members_tab(parent, notify):
    """Build the Members tab. Returns a function that reloads its table."""
    name = tk.StringVar()
    phone = tk.StringVar()
    search_text = tk.StringVar()

    # ---- Form ----
    form = ttk.Labelframe(parent, text=" Member Details ", padding=12)
    form.pack(fill="x", padx=10, pady=10)

    ttk.Label(form, text="Name").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    name_entry = ttk.Entry(form, textvariable=name, width=30)
    name_entry.grid(row=0, column=1, padx=5)
    ttk.Label(form, text="Phone").grid(row=0, column=2, padx=5, pady=5, sticky="w")
    phone_entry = ttk.Entry(form, textvariable=phone, width=20)
    phone_entry.grid(row=0, column=3, padx=5)

    # ---- Search bar ----
    search_frame = ttk.Frame(parent)
    search_frame.pack(fill="x", padx=10)
    ttk.Label(search_frame, text="🔍 Search:").pack(side="left")
    ttk.Entry(search_frame, textvariable=search_text,
              width=34).pack(side="left", padx=8)
    ttk.Label(search_frame, text="(type to filter by name or phone)",
              bootstyle="secondary").pack(side="left", padx=4)

    # ---- Table ----
    table = make_table(parent, ("ID", "Name", "Phone"), (60, 330, 200))
    count_label = ttk.Label(parent, text="", bootstyle="secondary")
    count_label.pack(anchor="w", padx=14, pady=(0, 6))

    def load_table(*args):
        """Show all members, or only those matching the search text."""
        keyword = search_text.get().strip().lower()
        rows = [m for m in db.get_members()
                if keyword in m[1].lower() or keyword in str(m[2])]
        fill_table(table, rows)
        count_label.configure(text=f"Showing {len(rows)} member(s)   •   "
                                   "right-click a row to copy the phone number")

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
        name_entry.focus()
        toast(f"Member '{n}' added.", "success")

    def copy_phone():
        selection = table.selection()
        if selection:
            table.clipboard_clear()
            table.clipboard_append(table.item(selection[0], "values")[2])
            toast("Phone number copied to clipboard.", "info")

    ttk.Button(form, text="Add Member", command=add_member,
               bootstyle="success").grid(row=0, column=4, padx=15)
    phone_entry.bind("<Return>", lambda e: add_member())   # Enter adds member
    add_context_menu(table, [("Copy phone number", copy_phone)])

    load_table()
    search_text.trace_add("write", load_table)
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
    ttk.Label(parent, text="Tip: double-click (or right-click) an issued book "
                           "to return it   •   overdue books are shown in red",
              bootstyle="secondary").pack(anchor="w", padx=14)

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
        fill_table(table, db.get_issued_books(), flag_col=7)

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
            toast(message, "success", "Book issued")
        else:
            messagebox.showerror("Cannot issue", message)
        refresh()
        notify()

    def return_book(event=None):
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
            toast(message, "warning" if fine > 0 else "success",
                  "Book returned")
        else:
            messagebox.showerror("Error", message)
        refresh()
        notify()

    ttk.Button(form, text="Issue Book", command=issue_book,
               bootstyle="success").grid(row=0, column=4, rowspan=2, padx=15)
    ttk.Button(parent, text="Return Selected Book", command=return_book,
               bootstyle="warning").pack(pady=(6, 10))
    table.bind("<Double-1>", return_book)       # double-click also returns
    add_context_menu(table, [("Return this book", return_book)])

    refresh()
    return refresh


# ------------------------------------------------------------- HISTORY TAB
def build_history_tab(parent):
    """Build the History tab (every issue ever made). Returns its refresh."""
    search_text = tk.StringVar()

    top = ttk.Frame(parent)
    top.pack(fill="x", padx=10, pady=(12, 0))
    ttk.Label(top, text="🔍 Search:").pack(side="left")
    ttk.Entry(top, textvariable=search_text, width=34).pack(side="left", padx=8)
    ttk.Label(top, text="(type a book or member name)",
              bootstyle="secondary").pack(side="left", padx=4)

    table = make_table(parent,
                       ("ID", "Book", "Member", "Issued", "Returned",
                        "Fine (Rs)", "Status"),
                       (60, 240, 170, 100, 100, 90, 100))
    count_label = ttk.Label(parent, text="", bootstyle="secondary")
    count_label.pack(anchor="w", padx=14, pady=(0, 6))

    def refresh(*args):
        keyword = search_text.get().strip().lower()
        rows = [r for r in db.get_history()
                if keyword in r[1].lower() or keyword in r[2].lower()]
        fill_table(table, rows)
        count_label.configure(text=f"{len(rows)} record(s)   •   "
                                   "click a column heading to sort")

    search_text.trace_add("write", refresh)
    refresh()
    return refresh


# ------------------------------------------------------------- REPORTS TAB
def build_reports_tab(parent):
    """Usage meter, most-issued chart, fine total and CSV export."""
    top = ttk.Frame(parent)
    top.pack(fill="x", padx=10, pady=10)

    # ---- Meter: how many copies are currently on loan ----
    try:
        meter = ttk.Meter(top, metersize=190, padding=8, amountused=0,
                          amounttotal=100, metertype="semi", textright="%",
                          subtext="of copies on loan", bootstyle="info")
        meter.pack(side="left", padx=10)

        def set_meter(percent):
            meter.configure(amountused=percent)
    except Exception:
        # Simple progress bar if the Meter widget is not available
        box = ttk.Frame(top)
        box.pack(side="left", padx=10)
        meter_text = ttk.Label(box, text="0% of copies on loan",
                               font=("Helvetica", 13, "bold"))
        meter_text.pack(pady=(30, 8))
        bar = ttk.Progressbar(box, length=190, maximum=100,
                              bootstyle="info-striped")
        bar.pack()

        def set_meter(percent):
            bar["value"] = percent
            meter_text.configure(text=f"{percent}% of copies on loan")

    # ---- Numbers ----
    numbers = ttk.Labelframe(top, text=" Summary ", padding=15)
    numbers.pack(side="left", fill="both", expand=True, padx=10)
    fine_label = ttk.Label(numbers, text="", font=("Helvetica", 14, "bold"),
                           bootstyle="success")
    fine_label.pack(anchor="w", pady=3)
    issues_label = ttk.Label(numbers, text="", font=("Helvetica", 13))
    issues_label.pack(anchor="w", pady=3)
    overdue_label = ttk.Label(numbers, text="", font=("Helvetica", 13),
                              bootstyle="danger")
    overdue_label.pack(anchor="w", pady=3)

    # ---- Export buttons ----
    export = ttk.Labelframe(top, text=" Export to CSV ", padding=15)
    export.pack(side="left", padx=10)
    ttk.Button(export, text="📖 Books", width=14, bootstyle="primary-outline",
               command=lambda: export_csv(
                   "books.csv", ["ID", "Title", "Author", "Quantity"],
                   db.get_books())).pack(pady=3)
    ttk.Button(export, text="👤 Members", width=14, bootstyle="primary-outline",
               command=lambda: export_csv(
                   "members.csv", ["ID", "Name", "Phone"],
                   db.get_members())).pack(pady=3)
    ttk.Button(export, text="🕘 History", width=14, bootstyle="primary-outline",
               command=lambda: export_csv(
                   "history.csv",
                   ["ID", "Book", "Member", "Issued", "Returned",
                    "Fine (Rs)", "Status"],
                   db.get_history())).pack(pady=3)

    # ---- Bar chart of the most issued books ----
    chart_box = ttk.Labelframe(parent, text=" Most Issued Books ", padding=10)
    chart_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    canvas = tk.Canvas(chart_box, height=230, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    def draw_chart(event=None):
        """Draw horizontal bars using the colors of the current theme."""
        colors = ttk.Style().colors
        canvas.delete("all")
        canvas.configure(bg=colors.bg)
        data = db.get_top_books(5)
        width = canvas.winfo_width()
        if width < 50:
            width = 600
        if not data:
            canvas.create_text(width / 2, 100, fill=colors.fg,
                               font=("Helvetica", 13),
                               text="No books have been issued yet.")
            return
        biggest = max(count for _, count in data)
        bar_space = max(100, width - 320)
        y = 15
        for book_title, count in data:
            label = book_title if len(book_title) <= 24 else book_title[:22] + "…"
            canvas.create_text(10, y + 15, text=label, anchor="w",
                               fill=colors.fg, font=("Helvetica", 12))
            bar = max(6, int(bar_space * count / biggest))
            canvas.create_rectangle(230, y, 230 + bar, y + 30,
                                    fill=colors.primary, outline="")
            canvas.create_text(230 + bar + 10, y + 15, text=f"{count}x",
                               anchor="w", fill=colors.fg,
                               font=("Helvetica", 12, "bold"))
            y += 42

    canvas.bind("<Configure>", draw_chart)

    def refresh():
        """Recalculate every number and redraw the chart."""
        available = sum(b[3] for b in db.get_books())
        issued = len(db.get_issued_books())
        total = available + issued
        percent = round(issued * 100 / total) if total else 0
        set_meter(percent)

        overdue = [r for r in db.get_issued_books()
                   if r[7].startswith("Overdue")]
        fine_label.configure(text=f"Total fine collected:  Rs {db.get_total_fine()}")
        issues_label.configure(text=f"Total issues made:  {len(db.get_history())}")
        overdue_label.configure(text=f"Overdue right now:  {len(overdue)} book(s)")
        draw_chart()

    refresh()
    return refresh


# -------------------------------------------------------------- DASHBOARD
def make_stat_card(parent, caption, color, on_click):
    """
    Colored card with a big number. Clicking it runs on_click().
    Returns (card, StringVar holding the number).
    """
    value = tk.StringVar(value="0")
    card = ttk.Frame(parent, bootstyle=color, padding=12)
    ttk.Label(card, textvariable=value, font=("Helvetica", 26, "bold"),
              bootstyle=f"inverse-{color}").pack()
    ttk.Label(card, text=caption, font=("Helvetica", 11),
              bootstyle=f"inverse-{color}").pack()
    for widget in (card, *card.winfo_children()):
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda e: on_click())
    return card, value


def animate_number(widget, var, target, steps=12):
    """Count smoothly from the current number up (or down) to target."""
    try:
        start = int(var.get())
    except ValueError:
        start = 0
    if start == target:
        return

    def step(i=1):
        var.set(str(round(start + (target - start) * i / steps)))
        if i < steps:
            widget.after(30, lambda: step(i + 1))

    step()


def show_dashboard(root):
    """Main screen: header, statistic cards and the tabs."""
    root.title("Library Management System")
    center_window(root, 1040, 810)

    page = ttk.Frame(root)
    page.pack(fill="both", expand=True)

    # ---- Header: title + clock on the left, theme picker + logout right ----
    header = ttk.Frame(page)
    header.pack(fill="x", padx=15, pady=(12, 5))

    left = ttk.Frame(header)
    left.pack(side="left")
    ttk.Label(left, text="📚 Library Management System",
              font=("Helvetica", 20, "bold"),
              bootstyle="primary").pack(anchor="w")
    clock = ttk.Label(left, text="", bootstyle="secondary")
    clock.pack(anchor="w")

    def tick():
        """Update the clock every second (stops when the page is closed)."""
        if not clock.winfo_exists():
            return
        clock.configure(text="Welcome, Admin   •   " +
                        datetime.now().strftime("%A, %d %b %Y   %I:%M:%S %p"))
        clock.after(1000, tick)

    shortcut_keys = []       # keyboard shortcuts, removed again on logout

    def logout():
        if messagebox.askyesno("Logout", "Do you want to log out?"):
            for sequence in shortcut_keys:
                root.unbind(sequence)
            page.destroy()
            show_login(root)

    ttk.Button(header, text="Logout", command=logout,
               bootstyle="danger-outline").pack(side="right")

    theme_box = ttk.Combobox(header, values=THEMES, width=11,
                             state="readonly")
    theme_box.set(root.style.theme.name)
    theme_box.pack(side="right", padx=8)
    ttk.Label(header, text="🎨 Theme").pack(side="right")

    def change_theme(event=None):
        """Apply the theme chosen in the dropdown."""
        root.style.theme_use(theme_box.get())
        apply_table_style(root)
        theme_box.selection_clear()
        on_tab_change()          # redraw tables and chart in the new colors

    theme_box.bind("<<ComboboxSelected>>", change_theme)

    # ---- Footer with hints (packed first so it stays at the bottom) ----
    ttk.Label(page, bootstyle="secondary",
              text="⌨  ⌘1 Books  •  ⌘2 Members  •  ⌘3 Issue/Return  •  "
                   "⌘4 History  •  ⌘5 Reports      "
                   "Right-click a row for more options").pack(side="bottom",
                                                              pady=(0, 6))

    # ---- Statistic cards (click a card to open its tab) ----
    cards = ttk.Frame(page)
    cards.pack(fill="x", padx=15, pady=8)

    card1, total_titles = make_stat_card(
        cards, "Book Titles", "primary", lambda: notebook.select(books_tab))
    card2, total_copies = make_stat_card(
        cards, "Copies Available", "success", lambda: notebook.select(books_tab))
    card3, total_members = make_stat_card(
        cards, "Members", "info", lambda: notebook.select(members_tab))
    card4, total_issued = make_stat_card(
        cards, "Currently Issued", "warning", lambda: notebook.select(issue_tab))
    for card in (card1, card2, card3, card4):
        card.pack(side="left", fill="x", expand=True, padx=5)

    def refresh_stats():
        """Recalculate the numbers on the cards (with a counting animation)."""
        books = db.get_books()
        animate_number(page, total_titles, len(books))
        animate_number(page, total_copies, sum(b[3] for b in books))
        animate_number(page, total_members, len(db.get_members()))
        animate_number(page, total_issued, len(db.get_issued_books()))

    # ---- Tabs ----
    notebook = ttk.Notebook(page, bootstyle="primary")
    notebook.pack(fill="both", expand=True, padx=15, pady=(5, 8))

    books_tab = ttk.Frame(notebook)
    members_tab = ttk.Frame(notebook)
    issue_tab = ttk.Frame(notebook)
    history_tab = ttk.Frame(notebook)
    reports_tab = ttk.Frame(notebook)

    notebook.add(books_tab, text=" 📖 Books ")
    notebook.add(members_tab, text=" 👤 Members ")
    notebook.add(issue_tab, text=" 🔄 Issue / Return ")
    notebook.add(history_tab, text=" 🕘 History ")
    notebook.add(reports_tab, text=" 📊 Reports ")

    refresh_books = build_books_tab(books_tab, refresh_stats)
    refresh_members = build_members_tab(members_tab, refresh_stats)
    refresh_issue = build_issue_tab(issue_tab, refresh_stats)
    refresh_history = build_history_tab(history_tab)
    refresh_reports = build_reports_tab(reports_tab)

    def on_tab_change(event=None):
        """Reload data when a tab is opened so every tab is up to date."""
        refresh_books()
        refresh_members()
        refresh_issue()
        refresh_history()
        refresh_reports()
        refresh_stats()

    notebook.bind("<<NotebookTabChanged>>", on_tab_change)

    # ---- Keyboard shortcuts: Cmd+1..5 (and Ctrl+1..5) switch tabs ----
    for number, tab in enumerate(
            (books_tab, members_tab, issue_tab, history_tab, reports_tab), 1):
        for prefix in ("Command", "Control"):
            sequence = f"<{prefix}-Key-{number}>"
            root.bind(sequence, lambda e, t=tab: notebook.select(t))
            shortcut_keys.append(sequence)

    refresh_stats()
    apply_table_style(root)
    tick()

    # ---- Overdue alert when the dashboard opens ----
    overdue = [r for r in db.get_issued_books() if r[7].startswith("Overdue")]
    if overdue:
        root.after(600, lambda: toast(
            f"{len(overdue)} book(s) are overdue! Open the Issue / Return tab.",
            "danger", "Overdue alert"))


# ------------------------------------------------------------------ START
if __name__ == "__main__":
    app = ttk.Window(themename=START_THEME)
    apply_table_style(app)
    show_login(app)
    app.mainloop()