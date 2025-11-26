import os
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog


python_files = ["studjeso.py", "jeso.py"]

compile_tmp = "compile_tmp"

def py_t_ex(python_file, output_folder):
    subprocess.run([
        'pyinstaller',
        '--onefile',
        '--distpath', output_folder,
        '--workpath', compile_tmp,
        '--specpath', compile_tmp, 
        python_file
    ])

def choose_folder():

    root = tk.Tk()
    root.withdraw()
    return filedialog.askdirectory(title="Выберите папку для сохранения приложений")

def clean_all_trash():
    trash = ["build", "dist", compile_tmp, "studjeso", "jeso"]
    for folder in trash:
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True) # удаление н папк

def dw_com():
    for file in python_files:
        if os.path.exists(file):
            py_t_ex(file, destination_folder)
        else:
            print(f"{file} не найден!")


destination_folder = choose_folder()

dw_com()
clean_all_trash()

print("Готово! .exe файлы скомпилированы и все лишние папки удалены.")
