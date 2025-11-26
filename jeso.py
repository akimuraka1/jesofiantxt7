#!/usr/bin/env python3

import os
import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

def create_db_if_not_exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        subject TEXT,
        difficulty TEXT,
        created_at TEXT
    )
    """)


    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        qtext TEXT NOT NULL,
        opt1 TEXT, opt2 TEXT, opt3 TEXT, opt4 TEXT, opt5 TEXT, opt6 TEXT,
        correct_index INTEGER,
        FOREIGN KEY(test_id) REFERENCES tests(id)
    )
    """)


    cur.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER,
        student_name TEXT,
        score INTEGER,
        total INTEGER,
        details TEXT,
        taken_at TEXT,
        FOREIGN KEY(test_id) REFERENCES tests(id)
    )
    """)


    cur.execute("""
    CREATE TABLE IF NOT EXISTS sketches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        result_id INTEGER,
        student_name TEXT,
        sketch BLOB,
        created_at TEXT,
        FOREIGN KEY(result_id) REFERENCES results(id)
    )
    """)


    conn.commit()
    return conn

def insert_test(conn, title, subject, difficulty):
    cur = conn.cursor()
    cur.execute("INSERT INTO tests (title, subject, difficulty, created_at) VALUES (?, ?, ?, ?)",
                (title, subject, difficulty, datetime.utcnow().isoformat()))
    conn.commit()
    return cur.lastrowid

def insert_question(conn, test_id, qtext, options, correct_index):
    opts = options + [None] * (6 - len(options))
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO questions (test_id, qtext, opt1, opt2, opt3, opt4, opt5, opt6, correct_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (test_id, qtext, *opts, correct_index))
    conn.commit()

def get_tests(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, title, subject, difficulty FROM tests ORDER BY id")
    return cur.fetchall()

def get_questions_for_test(conn, test_id):
    cur = conn.cursor()
    cur.execute("SELECT id, qtext, opt1, opt2, opt3, opt4, opt5, opt6, correct_index FROM questions WHERE test_id=? ORDER BY id", (test_id,))
    rows = cur.fetchall()
    out = []
    for row in rows:
        qid = row[0]
        qtext = row[1]
        opts = [row[i] for i in range(2, 8) if row[i] is not None]
        correct = row[8]
        out.append((qid, qtext, opts, correct))
    return out

def delete_test_and_questions(conn, test_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM questions WHERE test_id=?", (test_id,))
    cur.execute("DELETE FROM tests WHERE id=?", (test_id,))
    conn.commit()

def get_results_for_test(conn, test_id):
    cur = conn.cursor()
    cur.execute("SELECT student_name, score, total, taken_at FROM results WHERE test_id=? ORDER BY taken_at DESC", (test_id,))
    return cur.fetchall()

def get_sketch_for_result(conn, result_id):
    cur = conn.cursor()
    cur.execute("SELECT sketch FROM sketches WHERE result_id=?", (result_id,))
    row = cur.fetchone()
    if row and row[0]:
        from io import BytesIO
        from PIL import Image #такой имп больш зашел перешл на прямое рисование а не фото
        return Image.open(BytesIO(row[0]))
    return None

class jeso: # ui
    def __init__(self, root):
        self.root = root
        root.title("jeso")
        root.geometry("1000x660")
        root.configure(bg="#111111")

        self.db_path = None
        self.conn = None
        self.tests_map = {}
        self.current_test_id = None

        self._build_top_bar()
        self._build_main_area()

    def _build_top_bar(self): # верхх
        top = tk.Frame(self.root, bg="#111111")
        top.pack(fill=tk.X, padx=8, pady=8)

        btn_new_db = tk.Button(top, text="Создать новый .db", bg="#2b8", fg="white", command=self.create_new_db)
        btn_open_db = tk.Button(top, text="Открыть .db", bg="#444", fg="white", command=self.open_db)
        btn_quit = tk.Button(top, text="Выход", bg="#333", fg="white", command=self.root.quit)
        btn_view_sketches = tk.Button(top, text="Просмотр черновиков", bg="#555", fg="white", command=self.view_sketches)
        btn_merge_db = tk.Button(top, text="Объединить БД", bg="#2a8", fg="white", command=self.merge_databases) # кнопочки


        btn_new_db.pack(side=tk.LEFT, padx=4)
        btn_open_db.pack(side=tk.LEFT, padx=4)
        btn_quit.pack(side=tk.RIGHT, padx=4)
        btn_view_sketches.pack(side=tk.LEFT, padx=4)
        btn_merge_db.pack(side=tk.LEFT, padx=4) # создание кнопочек

        self.label_db = tk.Label(top, text="БД: не загружена", bg="#111111", fg="#ddd")
        self.label_db.pack(side=tk.LEFT, padx=8)

    def _build_main_area(self): # осн часть
        main = tk.Frame(self.root, bg="#111111")
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        left = tk.Frame(main, bg="#111111")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)

        tk.Label(left, text="Тесты в базе:", bg="#111111", fg="white").pack(anchor='w')
        self.tests_listbox = tk.Listbox(left, width=40, bg="#222222", fg="white", selectbackground="#555555")
        self.tests_listbox.pack(pady=6, fill=tk.Y, expand=True)
        self.tests_listbox.bind("<<ListboxSelect>>", self.on_test_select)

        right = tk.Frame(main, bg="#111111")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)

        btn_frame = tk.Frame(right, bg="#111111")
        btn_frame.pack(fill=tk.X, pady=6) # кнопки управл
        tk.Button(btn_frame, text="Создать новый тест", bg="#2b8", fg="white", command=self.create_test_wizard).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Просмотр вопросов", bg="#444", fg="white", command=self.view_questions_of_selected).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Удалить тест", bg="#a33", fg="white", command=self.delete_selected_test).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Просмотреть результаты", bg="#444", fg="white", command=self.view_results_of_selected).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Обновить список", bg="#555", fg="white", command=self.refresh_tests_list).pack(side=tk.LEFT, padx=4)


        info_frame = tk.Frame(right, bg="#111111")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=8) # инф панель

        self.info_label = tk.Label(info_frame, text="Выберите файл БД и создайте тесты.\n\nВ БД можно хранить множество тестов.", justify='left', bg="#111111", fg="#ddd")
        self.info_label.pack(anchor='nw', padx=6, pady=6)

    def create_new_db(self):
        path = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("SQLite DB", "*.db")])
        if not path:
            return
        self.conn = create_db_if_not_exists(path)
        self.db_path = path
        self.label_db.config(text=f"БД: {os.path.basename(path)}")
        messagebox.showinfo("Создано", f"Создан файл базы: {path}")
        self.refresh_tests_list()

    def open_db(self):
        path = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db")])
        if not path:
            return
        self.conn = create_db_if_not_exists(path)
        self.db_path = path
        self.label_db.config(text=f"БД: {os.path.basename(path)}")
        messagebox.showinfo("Открыто", f"Открыт файл базы: {path}")
        self.refresh_tests_list()

    def refresh_tests_list(self): # обновлени на всякий 
        if not self.conn:
            messagebox.showwarning("Нет БД", "Сначала создайте или откройте файл .db")
            return
        self.tests_listbox.delete(0, tk.END)
        tests = get_tests(self.conn)
        self.tests_map = {}
        for t in tests:
            tid, title, subject, diff = t
            disp = f"[{tid}] {title} — {subject} ({diff})"
            self.tests_map[tid] = disp
            self.tests_listbox.insert(tk.END, disp)
        self.info_label.config(text=f"Загружено тестов: {len(tests)}")

    def merge_databases(self):
        files = filedialog.askopenfilenames(title="Выберите файлы БД для объединения", filetypes=[("SQLite DB","*.db")])
        if not files:
            return

        new_db_path = filedialog.asksaveasfilename(title="Создать объединённую БД", defaultextension=".db", filetypes=[("SQLite DB","*.db")])
        if not new_db_path:
            return

        conn = create_db_if_not_exists(new_db_path)
        cur = conn.cursor()
        merged_tests_count = 0

        for file in files:
            try:
                src_conn = sqlite3.connect(file)
                src_cur = src_conn.cursor()

                src_cur.execute("SELECT id, title, subject, difficulty, created_at FROM tests")
                for test_id, title, subject, difficulty, created_at in src_cur.fetchall():
                    cur.execute("SELECT id FROM tests WHERE title=? AND subject=?", (title, subject))
                    row = cur.fetchone()
                    new_test_id = row[0] if row else None
                    if not new_test_id:
                        cur.execute("INSERT INTO tests (title, subject, difficulty, created_at) VALUES (?, ?, ?, ?)",
                                    (title, subject, difficulty, created_at))
                        new_test_id = cur.lastrowid

                    src_cur.execute("SELECT qtext, opt1, opt2, opt3, opt4, opt5, opt6, correct_index FROM questions WHERE test_id=?", (test_id,))
                    for q in src_cur.fetchall():
                        qtext = q[0]
                        cur.execute("SELECT id FROM questions WHERE test_id=? AND qtext=?", (new_test_id, qtext))
                        if not cur.fetchone():
                            cur.execute("""
                                INSERT INTO questions (test_id, qtext, opt1, opt2, opt3, opt4, opt5, opt6, correct_index)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (new_test_id, *q))

                    # Копир результатов с избежанием дубл
                    src_cur.execute("SELECT student_name, score, total, details, taken_at FROM results WHERE test_id=?", (test_id,))
                    for r in src_cur.fetchall():
                        student_name, score, total, details, taken_at = r
                        cur.execute("SELECT id FROM results WHERE test_id=? AND student_name=? AND taken_at=?",
                                    (new_test_id, student_name, taken_at))
                        if not cur.fetchone():
                            cur.execute("INSERT INTO results (test_id, student_name, score, total, details, taken_at) VALUES (?, ?, ?, ?, ?, ?)",
                                        (new_test_id, student_name, score, total, details, taken_at))

                    src_cur.execute("SELECT student_name, sketch, created_at, result_id FROM sketches WHERE result_id IN (SELECT id FROM results WHERE test_id=?)", (test_id,))
                    for s in src_cur.fetchall():
                        student_name, sketch, created_at, src_result_id = s
                        cur.execute("SELECT id FROM results WHERE test_id=? AND student_name=? ORDER BY taken_at DESC LIMIT 1",
                                    (new_test_id, student_name))
                        res_row = cur.fetchone()
                        if res_row:
                            new_result_id = res_row[0]
                            cur.execute("SELECT id FROM sketches WHERE result_id=? AND student_name=? AND created_at=?", # если ужееее есть
                                        (new_result_id, student_name, created_at))
                            if not cur.fetchone():
                                cur.execute("INSERT INTO sketches (result_id, student_name, sketch, created_at) VALUES (?, ?, ?, ?)",
                                            (new_result_id, student_name, sketch, created_at))

                    merged_tests_count += 1
                conn.commit()
                src_conn.close()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось объединить {file}: {e}")

        messagebox.showinfo("Готово", f"Объединение завершено. Создан файл: {new_db_path}. Обработано тестов: {merged_tests_count}.")



# fgrf

    def on_test_select(self, event):
        sel = self.tests_listbox.curselection()
        if not sel:
            self.current_test_id = None
            return
        index = sel[0]
        try:
            tid = list(self.tests_map.keys())[index]  # создание
            self.current_test_id = tid
        except Exception:
            self.current_test_id = None
    def create_test_wizard(self):
        if not self.conn:
            messagebox.showwarning("Нет БД", "Создайте или откройте файл .db сначала.")
            return

        wizard = tk.Toplevel(self.root)
        wizard.title("Создание теста")
        wizard.geometry("800x680")
        wizard.configure(bg="#111111")

        meta_frame = tk.Frame(wizard, bg="#111111")
        meta_frame.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(meta_frame, text="Название теста:", bg="#111111", fg="white").grid(row=0, column=0, sticky='w')
        entry_title = tk.Entry(meta_frame, width=60, bg="#222222", fg="white")
        entry_title.grid(row=0, column=1, padx=6, pady=4)
        tk.Label(meta_frame, text="Предмет:", bg="#111111", fg="white").grid(row=1, column=0, sticky='w')
        entry_subject = tk.Entry(meta_frame, width=30, bg="#222222", fg="white")
        entry_subject.grid(row=1, column=1, sticky='w', padx=6, pady=4)
        tk.Label(meta_frame, text="Сложность:", bg="#111111", fg="white").grid(row=2, column=0, sticky='w')
        entry_diff = tk.Entry(meta_frame, width=20, bg="#222222", fg="white")
        entry_diff.grid(row=2, column=1, sticky='w', padx=6, pady=4)

        questions = []

        qpanel = tk.Frame(wizard, bg="#111111")
        qpanel.pack(fill=tk.BOTH, expand=True, padx=8, pady=6) # ввод

        tk.Label(qpanel, text="Текст вопроса:", bg="#111111", fg="white").pack(anchor='w')
        qtext_box = tk.Text(qpanel, height=4, bg="#222222", fg="white")
        qtext_box.pack(fill=tk.X, pady=6)

        option_entries = []
        for i in range(6):
            f = tk.Frame(qpanel, bg="#111111")
            f.pack(fill=tk.X, pady=2)
            tk.Label(f, text=f"Вариант {i+1}:", bg="#111111", fg="white", width=10).pack(side=tk.LEFT)
            ent = tk.Entry(f, bg="#222222", fg="white", width=80)
            ent.pack(side=tk.LEFT, padx=6)
            option_entries.append(ent)

        tk.Label(qpanel, text="Правильный вариант (1-6):", bg="#111111", fg="white").pack(anchor='w', pady=6)
        correct_var = tk.IntVar(value=1)
        correct_spin = tk.Spinbox(qpanel, from_=1, to=6, textvariable=correct_var, width=5)
        correct_spin.pack(anchor='w')

        info_label = tk.Label(wizard, text="Добавлено вопросов: 0", bg="#111111", fg="white")
        info_label.pack(anchor='w', padx=8, pady=6)

        btn_frame = tk.Frame(wizard, bg="#111111")
        btn_frame.pack(fill=tk.X, padx=8, pady=6)

        def add_question_action():
            qtxt = qtext_box.get("1.0", tk.END).strip()
            opts = [e.get().strip() for e in option_entries if e.get().strip() != ""]
            corr = correct_var.get() - 1
            if not qtxt:
                messagebox.showwarning("Ошибка", "Поле вопроса не может быть пустым.")
                return
            if len(opts) == 0:
                messagebox.showwarning("Ошибка", "Добавьте хотя бы один вариант ответа.")
                return
            if corr < 0 or corr >= len(opts):
                messagebox.showwarning("Ошибка", "Правильный вариант должен соответствовать одному из введённых вариантов.")
                return
            questions.append((qtxt, opts, corr))
            info_label.config(text=f"Добавлено вопросов: {len(questions)}")
            qtext_box.delete("1.0", tk.END)
            for e in option_entries:
                e.delete(0, tk.END)
            correct_var.set(1)

        def finish_and_save():
            title = entry_title.get().strip()
            subject = entry_subject.get().strip()
            diff = entry_diff.get().strip()
            if not title:
                messagebox.showwarning("Ошибка", "Укажите название теста.")
                return
            if not questions:
                messagebox.showwarning("Ошибка", "Добавьте хотя бы один вопрос.")
                return
            test_id = insert_test(self.conn, title, subject, diff)
            for q in questions:
                insert_question(self.conn, test_id, q[0], q[1], q[2])
            messagebox.showinfo("Сохранено", f"Тест сохранён (id={test_id}).")
            wizard.destroy()
            self.refresh_tests_list()

        btn_add = tk.Button(btn_frame, text="Добавить вопрос", bg="#2b8", fg="white", command=add_question_action)
        btn_add.pack(side=tk.LEFT, padx=6)
        btn_finish = tk.Button(btn_frame, text="Завершить и сохранить тест", bg="#2b8", fg="white", command=finish_and_save)
        btn_finish.pack(side=tk.LEFT, padx=6)

    def view_questions_of_selected(self): # начало просмотр
        """Открывает окно просмотра вопросов выбранного теста (только просмотр)."""
        if not self.conn:
            messagebox.showwarning("Нет БД", "Откройте файл .db")
            return
        sel = self.tests_listbox.curselection()
        if not sel:
            messagebox.showwarning("Не выбран тест", "Выберите тест в списке.")
            return
        tid = list(self.tests_map.keys())[sel[0]]
        qs = get_questions_for_test(self.conn, tid)
        win = tk.Toplevel(self.root)
        win.title(f"Вопросы теста [{tid}]")
        win.geometry("820x600")
        win.configure(bg="#111111")

        canvas = tk.Canvas(win, bg="#111111")
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(win, command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = tk.Frame(canvas, bg="#111111")
        canvas.create_window((0,0), window=inner, anchor='nw')

        def on_config(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", on_config)

        for i, q in enumerate(qs, 1):
            qid, qtext, opts, corr = q
            f = tk.Frame(inner, bg="#222222", pady=6)
            f.pack(fill=tk.X, padx=6, pady=6)
            tk.Label(f, text=f"{i}. {qtext}", fg="white", bg="#222222", wraplength=760, justify='left').pack(anchor='w', padx=6, pady=2)
            for oi, opt in enumerate(opts, 1):
                mark = " (правильно)" if (oi-1)==corr else ""
                tk.Label(f, text=f"   {oi}) {opt}{mark}", fg="#ddd", bg="#222222", wraplength=760, justify='left').pack(anchor='w', padx=12)

    def delete_selected_test(self): # удаление самого тест
        if not self.conn:
            return
        sel = self.tests_listbox.curselection()
        if not sel:
            messagebox.showwarning("Не выбран тест", "Выберите тест.")
            return
        tid = list(self.tests_map.keys())[sel[0]]
        if not messagebox.askyesno("Подтвердите удаление", "Удалить тест и все вопросы?"):
            return
        delete_test_and_questions(self.conn, tid)
        messagebox.showinfo("Удалено", "Тест удалён.")
        self.refresh_tests_list()

    def view_results_of_selected(self): # просмотр результатов
        if not self.conn:
            return
        sel = self.tests_listbox.curselection()
        if not sel:
            messagebox.showwarning("Не выбран тест", "Выберите тест.")
            return
        tid = list(self.tests_map.keys())[sel[0]]
        rows = get_results_for_test(self.conn, tid)
        win = tk.Toplevel(self.root)
        win.title("Результаты теста")
        win.geometry("700x400")
        win.configure(bg="#111111")
        tk.Label(win, text=f"Результаты теста id={tid}", fg="white", bg="#111111").pack(pady=6)
        if not rows:
            tk.Label(win, text="Результатов ещё нет.", fg="white", bg="#111111").pack(pady=6)
            return
        for r in rows:
            name, score, total, taken_at = r
            tk.Label(win, text=f"{taken_at[:19]} — {name}: {score}/{total}", fg="#ddd", bg="#111111").pack(anchor='w', padx=8)
        
    
    def view_sketches(self):
        if not self.conn:
            messagebox.showwarning("Нет БД", "Сначала откройте базу данных.")
            return
        sel = self.tests_listbox.curselection()
        if not sel:
            messagebox.showwarning("Не выбран тест", "Выберите тест в списке.")
            return
        tid = list(self.tests_map.keys())[sel[0]]

        cur = self.conn.cursor()
        cur.execute("SELECT id, student_name FROM results WHERE test_id=?", (tid,))
        results = cur.fetchall()
        if not results:
            messagebox.showinfo("Нет черновиков", "Нет результатов по этому тесту.")
            return

        win = tk.Toplevel(self.root)
        win.title(f"Черновики теста [{tid}]")
        win.geometry("800x600")
        canvas = tk.Canvas(win, bg="black")
        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar = tk.Scrollbar(win, command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=scrollbar.set)
        inner = tk.Frame(canvas, bg="#111111")
        canvas.create_window((0,0), window=inner, anchor='nw')
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        from PIL import Image, ImageTk
        import io
        self.sketch_images = []

        for rid, sname in results:
            cur.execute("SELECT sketch FROM sketches WHERE result_id=?", (rid,))
            row = cur.fetchone()
            if row and row[0]:
                img = Image.open(io.BytesIO(row[0]))
                img.thumbnail((780, 500))
                tk_img = ImageTk.PhotoImage(img)
                lbl = tk.Label(inner, image=tk_img, bg="#111111")
                lbl.pack(padx=6, pady=6)
                self.sketch_images.append(tk_img)
                tk.Label(inner, text=sname, fg="white", bg="#111111").pack(padx=6, pady=(0,8))

def main():
    root = tk.Tk()
    app = jeso(root)
    root.mainloop()

if __name__ == "__main__":
    main()
