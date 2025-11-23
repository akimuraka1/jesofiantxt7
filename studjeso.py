#!/usr/bin/env python3
"""
StudentApp.py — улучшенная версия для ученика с интеграцией черновика в базу

Функционал:
- Прохождение тестов и выбор ответов
- Черновик для заметок, который сохраняется автоматически в БД
- После завершения теста результаты и черновик сохраняются в таблицы results и sketches
- Совместимость с TeacherApp

Требования:
- SQLite
- Tkinter
- PIL (для сохранения Canvas)
"""

import os
import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import io

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# ----------------------------- БАЗА ДАННЫХ -----------------------------
def create_or_open_db(db_path):
    """
    Создаёт соединение с БД, если её нет — создаёт новые таблицы
    """
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

def get_tests(conn):
    """Возвращает список тестов"""
    cur = conn.cursor()
    cur.execute("SELECT id, title, subject, difficulty FROM tests ORDER BY id")
    return cur.fetchall()

def get_questions_for_test(conn, test_id):
    """Возвращает вопросы и варианты для выбранного теста"""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, qtext, opt1, opt2, opt3, opt4, opt5, opt6, correct_index
        FROM questions WHERE test_id=? ORDER BY id
    """, (test_id,))
    rows = cur.fetchall()
    out = []
    for row in rows:
        qid = row[0]
        qtext = row[1]
        opts = [row[i] for i in range(2, 8) if row[i] is not None]
        correct = row[8]
        out.append((qid, qtext, opts, correct))
    return out

def save_result_and_sketch(conn, test_id, student_name, score, total, sketch_img):
    cur = conn.cursor()

    # сохраняем результат
    cur.execute("""
        INSERT INTO results (test_id, student_name, score, total, taken_at)
        VALUES (?, ?, ?, ?, ?)
    """, (test_id, student_name, score, total, datetime.utcnow().isoformat()))
    result_id = cur.lastrowid

    # ------------------------------
    # Сохраняем черновик
    # ------------------------------
    if isinstance(sketch_img, str) and sketch_img == "NO_SKETCH":
        # записываем текстовый маркер
        cur.execute("""
            INSERT INTO sketches (result_id, student_name, sketch, created_at)
            VALUES (?, ?, ?, ?)
        """, (result_id, student_name, sketch_img.encode(), datetime.utcnow().isoformat()))

    else:
        # сохраняем PNG
        bio = io.BytesIO()
        sketch_img.save(bio, format="PNG")

        cur.execute("""
            INSERT INTO sketches (result_id, student_name, sketch, created_at)
            VALUES (?, ?, ?, ?)
        """, (result_id, student_name, bio.getvalue(), datetime.utcnow().isoformat()))

    conn.commit()


# ----------------------------- UI / Ученик -----------------------------
class StudentApp:
    def __init__(self, root):
        self.root = root
        root.title("StudentApp — Ученик")
        root.geometry("1000x660")
        root.configure(bg="#111111")

        self.conn = None
        self.db_path = None
        self.tests_map = {}
        self.current_test_id = None
        self.student_name = ""
        self.sketch_image = None  # PIL Image черновика
        self.sketch_draw = None    # объект ImageDraw для рисования

        self._build_top_bar()
        self._build_main_area()

    # ----------------- верхняя панель -----------------
    def _build_top_bar(self):
        top = tk.Frame(self.root, bg="#111111")
        top.pack(fill=tk.X, padx=8, pady=8)

        btn_open_db = tk.Button(top, text="Открыть .db", bg="#444", fg="white", command=self.open_db)
        # btn_sketch = tk.Button(top, text="Черновик", bg="#333", fg="white", command=self.open_sketch)
        btn_quit = tk.Button(top, text="Выход", bg="#333", fg="white", command=self.root.quit)

        btn_open_db.pack(side=tk.LEFT, padx=4)
        # btn_sketch.pack(side=tk.LEFT, padx=4)
        btn_quit.pack(side=tk.RIGHT, padx=4)

        self.label_db = tk.Label(top, text="БД: не загружена", bg="#111111", fg="#ddd")
        self.label_db.pack(side=tk.LEFT, padx=8)

        tk.Label(top, text="Ваше имя:", bg="#111111", fg="white").pack(side=tk.LEFT, padx=4)
        self.entry_name = tk.Entry(top, width=20, bg="#222222", fg="white")
        self.entry_name.pack(side=tk.LEFT, padx=4)

    # ----------------- основная область -----------------
    def _build_main_area(self):
        main = tk.Frame(self.root, bg="#111111")
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        left = tk.Frame(main, bg="#111111")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)

        tk.Label(left, text="Доступные тесты:", bg="#111111", fg="white").pack(anchor='w')
        self.tests_listbox = tk.Listbox(left, width=40, bg="#222222", fg="white", selectbackground="#555555")
        self.tests_listbox.pack(pady=6, fill=tk.Y, expand=True)
        self.tests_listbox.bind("<<ListboxSelect>>", self.on_test_select)

        right = tk.Frame(main, bg="#111111")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)

        btn_frame = tk.Frame(right, bg="#111111")
        btn_frame.pack(fill=tk.X, pady=6)

        tk.Button(btn_frame, text="Начать тест", bg="#2b8", fg="white", command=self.start_test).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Обновить список тестов", bg="#555", fg="white", command=self.refresh_tests_list).pack(side=tk.LEFT, padx=4)

        self.info_label = tk.Label(right, text="Выберите БД и тест для прохождения.", bg="#111111", fg="#ddd", justify='left')
        self.info_label.pack(anchor='nw', padx=6, pady=6)

    # ----------------- работа с БД -----------------
    def open_db(self):
        path = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db")])
        if not path:
            return
        self.conn = create_or_open_db(path)
        self.db_path = path
        self.label_db.config(text=f"БД: {os.path.basename(path)}")
        messagebox.showinfo("Открыто", f"БД открыта: {path}")
        self.refresh_tests_list()



    def refresh_tests_list(self):
        if not self.conn:
            messagebox.showwarning("Нет БД", "Сначала откройте файл .db")
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

    def on_test_select(self, event):
        sel = self.tests_listbox.curselection()
        if not sel:
            self.current_test_id = None
            return
        index = sel[0]
        self.current_test_id = list(self.tests_map.keys())[index]
    # def get_canvas_image(self, canvas):
    #     canvas.update()
    #     ps = canvas.postscript(colormode='color')
    #     img = Image.open(io.BytesIO(ps.encode('utf-8')))
    #     return img
    
 


    # ----------------- прохождение теста -----------------
    def start_test(self):
        if not self.current_test_id:
            messagebox.showwarning("Нет выбора", "Выберите тест.")
            return
        self.student_name = self.entry_name.get().strip()
        if not self.student_name:
            messagebox.showwarning("Введите имя", "Укажите ваше имя.")
            return
        questions = get_questions_for_test(self.conn, self.current_test_id)
        if not questions:
            messagebox.showinfo("Пусто", "В этом тесте нет вопросов.")
            return

        win = tk.Toplevel(self.root)
        win.title("Прохождение теста")
        win.geometry("900x660")
        win.configure(bg="#111111")

        canvas = tk.Canvas(win, bg="#111111")
        scrollbar = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#111111")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            # Windows
            if event.delta:
                canvas.yview_scroll(-1 * (event.delta // 120), "units")
            # Linux / Mac
            else:
                canvas.yview_scroll(event.delta, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)   # Windows/Mac
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))  # Linux scroll up
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))   # Linux scroll down


        self.selected_answers = []

        for idx, q in enumerate(questions, start=1):
            qid, qtext, opts, correct = q
            tk.Label(scroll_frame, text=f"Вопрос {idx}: {qtext}",
                bg="#111111", fg="#ddd",
                wraplength=800, justify="left", anchor='w',
                font=("Arial", 12)).pack(anchor='w', pady=6)


            var = tk.IntVar(value=-1)
            self.selected_answers.append((q, var))
            for i, opt in enumerate(opts):
                tk.Radiobutton(scroll_frame, text=opt, variable=var, value=i, bg="#111111", fg="#aaa", selectcolor="#444").pack(anchor='w', padx=20)

        




        def submit_answers():
            score = 0
            for q, var in self.selected_answers:
                _, _, _, correct = q
                if var.get() == correct:
                    score += 1

            # ---------------------------
            # Сохраняем черновик
            # ---------------------------
            # Если окно черновика открыто, берём текущее содержимое
            sketch_img = None
            if PIL_AVAILABLE and hasattr(self, "canvas_sketch") and self.canvas_sketch.winfo_exists():
                try:
                    # Получаем изображение с Canvas
                    sketch_img = self.get_canvas_image(self.canvas_sketch)
                    # Сохраняем его в self.sketch_image, чтобы потом тоже можно было использовать
                    self.sketch_image = sketch_img
                except Exception as e:
                    print("Ошибка сохранения черновика:", e)
                    sketch_img = None
            else:
                # Если окно черновика закрыто, используем ранее сохранённое изображение
                sketch_img = getattr(self, "sketch_image", None)

            if sketch_img is None:
                sketch_img = "NO_SKETCH"

            # ---------------------------
            # Сохраняем результат и черновик в БД
            # ---------------------------
            save_result_and_sketch(
                self.conn,
                self.current_test_id,
                self.student_name,
                score,
                len(self.selected_answers),
                sketch_img
            )

            # ---------------------------
            # Закрываем окно черновика, если оно открыто
            # ---------------------------
            if hasattr(self, "canvas_sketch") and self.canvas_sketch.winfo_exists():
                self.canvas_sketch.master.destroy()

            messagebox.showinfo("Результат", f"Вы набрали {score}/{len(self.selected_answers)}")
            win.destroy()






        btn_frame = tk.Frame(win, bg="#111111")
        btn_frame.pack(fill="x", pady=6)

        tk.Button(btn_frame, text="Завершить тест", bg="#2b8", fg="white", command=submit_answers).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Черновик", bg="#555", fg="white", command=self.open_sketch_window).pack(side=tk.LEFT, padx=4)

    # -----------------------------
    # Вспомогательная функция для черновика
    # -----------------------------
    




    # аааа
    def open_sketch_window(self):
        if not PIL_AVAILABLE:
            messagebox.showwarning("PIL отсутствует", "Невозможно открыть черновик — нет PIL.")
            return

        # если уже создано окно черновика, просто поднимаем его
        if hasattr(self, "sketch_win") and self.sketch_win.winfo_exists():
            self.sketch_win.lift()
            return

        self.sketch_win = tk.Toplevel(self.root)
        self.sketch_win.title("Черновик")
        self.sketch_win.geometry("820x240")
        self.sketch_win.transient(self.root)
        self.sketch_win.attributes("-topmost", True)

        # создаём Canvas
        self.canvas_sketch = tk.Canvas(self.sketch_win, bg="white", width=800, height=200)
        self.canvas_sketch.pack(padx=10, pady=10)

        # создаём PIL Image для параллельного рисования
        self.sketch_image = Image.new("RGB", (800, 200), "white")
        self.sketch_draw = ImageDraw.Draw(self.sketch_image)

        drawing = {"x": None, "y": None}

        def start_draw(event):
            drawing["x"], drawing["y"] = event.x, event.y

        def draw(event):
            if drawing["x"] is not None:
                # Canvas
                self.canvas_sketch.create_line(drawing["x"], drawing["y"], event.x, event.y, fill="black", width=2)
                # PIL Image
                self.sketch_draw.line((drawing["x"], drawing["y"], event.x, event.y), fill="black", width=2)
                drawing["x"], drawing["y"] = event.x, event.y

        def end_draw(event):
            drawing["x"], drawing["y"] = None, None

        self.canvas_sketch.bind("<Button-1>", start_draw)
        self.canvas_sketch.bind("<B1-Motion>", draw)
        self.canvas_sketch.bind("<ButtonRelease-1>", end_draw)







# ----------------------------- запуск приложения -----------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = StudentApp(root)
    root.mainloop()
