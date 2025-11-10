import tkinter as tk
from threading import Thread
import socket
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import ipaddress

# ---------------- AES Функции ----------------
aes_key = AESGCM.generate_key(bit_length=256)
aes = AESGCM(aes_key)

def encrypt_message(msg: str) -> bytes:
    iv = os.urandom(12)
    ct = aes.encrypt(iv, msg.encode(), None)
    return iv + ct

def decrypt_message(data: bytes) -> str:
    iv = data[:12]
    ct = data[12:]
    return aes.decrypt(iv, ct, None).decode()

# ---------------- GUI ----------------
root = tk.Tk()
root.title("🔒 Secure Chat")
root.configure(bg="black")
root.geometry("550x500")

# ---------------- Первая форма: выбор режима ----------------
mode_frame = tk.Frame(root, bg="black")
mode_frame.pack(pady=20)

tk.Label(mode_frame, text="Выберите режим подключения:", bg="black", fg="white", font=("Arial", 12)).pack(pady=5)
selected_mode = tk.StringVar(value="LAN")
tk.Radiobutton(mode_frame, text="Локальная сеть (LAN)", variable=selected_mode, value="LAN", bg="black", fg="white", selectcolor="gray").pack()
tk.Radiobutton(mode_frame, text="Сервер / VPN", variable=selected_mode, value="SERVER", bg="black", fg="white", selectcolor="gray").pack()

def next_step():
    mode_frame.pack_forget()
    show_connection_frame()

next_button = tk.Button(mode_frame, text="Далее", bg="#444444", fg="white", command=next_step)
next_button.pack(pady=10)

# ---------------- Форма подключения ----------------
connect_frame = tk.Frame(root, bg="black")
status_label = tk.Label(connect_frame, text="", bg="black", fg="lightgreen")

ip_entry = tk.Entry(connect_frame, bg="#222222", fg="white")
port_entry = tk.Entry(connect_frame, bg="#222222", fg="white")
connect_button = tk.Button(connect_frame, text="Connect", bg="#444444", fg="white", command=lambda: Thread(target=connect).start())

def show_connection_frame():
    connect_frame.pack(pady=10)
    
    if selected_mode.get() == "SERVER":
        tk.Label(connect_frame, text="IP сервера (VPN):", bg="black", fg="white").grid(row=0, column=0, sticky="w")
    else:
        tk.Label(connect_frame, text="Ваш локальный IP:", bg="black", fg="white").grid(row=0, column=0, sticky="w")
        
    ip_entry.grid(row=0, column=1, padx=5)
    tk.Label(connect_frame, text="Порт:", bg="black", fg="white").grid(row=1, column=0, sticky="w")
    port_entry.grid(row=1, column=1, padx=5)
    status_label.grid(row=2, column=0, columnspan=2, pady=5)
    connect_button.grid(row=3, column=0, columnspan=2, pady=5)

# ---------------- Форма чата ----------------
chat_frame = tk.Frame(root, bg="black")
text_area = tk.Text(chat_frame, bg="black", fg="white")
text_area.pack(expand=True, fill=tk.BOTH)
entry = tk.Entry(chat_frame, bg="#222222", fg="white", insertbackground="white")
entry.pack(fill=tk.X)
send_button = tk.Button(chat_frame, text="Send", bg="#444444", fg="white", command=lambda: send_message())
send_button.pack(fill=tk.X)

def display_encrypted_message(msg: str):
    text_area.insert(tk.END, f"Encrypted: {msg}\n")
    text_area.see(tk.END)

def display_decrypted_message(msg: str, sender="You"):
    text_area.insert(tk.END, f"{sender}: {msg}\n")
    text_area.see(tk.END)

def receive_messages(sock):
    while True:
        try:
            data = sock.recv(4096)
            if data:
                display_encrypted_message(data.hex())
                msg = decrypt_message(data)
                display_decrypted_message(msg, sender="Peer")
        except:
            break

def send_message():
    msg = entry.get()
    if not msg:
        return
    encrypted = encrypt_message(msg)
    active_socket.sendall(encrypted)
    display_encrypted_message(encrypted.hex())
    display_decrypted_message(msg)
    entry.delete(0, tk.END)

def is_valid_ip(ip_str):
    try:
        ipaddress.ip_address(ip_str)
        return True
    except:
        return False

def connect():
    global active_socket
    HOST = ip_entry.get()
    PORT_STR = port_entry.get()

    # Проверка порта
    if not PORT_STR.isdigit():
        status_label.config(text="Порт должен быть числом", fg="red")
        return
    PORT = int(PORT_STR)
    if PORT < 1024 or PORT > 65535:
        status_label.config(text="Порт должен быть от 1024 до 65535", fg="red")
        return

    # Проверка IP
    if not is_valid_ip(HOST):
        status_label.config(text="Неверный IP адрес", fg="red")
        return

    try:
        if selected_mode.get() == "SERVER":
            # Клиентский режим: подключаемся к серверу
            active_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            active_socket.connect((HOST, PORT))
            status_label.config(text=f"Подключено к серверу {HOST}:{PORT}", fg="lightgreen")
        else:
            # LAN: сначала пробуем клиент
            try:
                active_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                active_socket.connect((HOST, PORT))
                status_label.config(text=f"Подключено к LAN {HOST}:{PORT}", fg="lightgreen")
            except:
                # Если не удалось — становимся сервером
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.bind(("0.0.0.0", PORT))
                server_socket.listen(1)
                status_label.config(text=f"Ожидание подключения LAN на {HOST}:{PORT}", fg="yellow")
                conn, addr = server_socket.accept()
                status_label.config(text=f"Подключился {addr}", fg="lightgreen")
                active_socket = conn
    except Exception as e:
        status_label.config(text=f"Ошибка подключения: {e}", fg="red")
        return

    connect_frame.pack_forget()
    chat_frame.pack(expand=True, fill=tk.BOTH)
    Thread(target=receive_messages, args=(active_socket,), daemon=True).start()

root.mainloop()
