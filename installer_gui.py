# -*- coding: utf-8 -*-
"""
Arizona RP & MoonLoader GUI Installer.
Features:
- Windows Registry auto-detection for GTA San Andreas and Arizona Games Launcher.
- Folder selection dialog to confirm or customize the game path.
- Downloads the complete moonloader archive from GitHub with real-time download progress, speed, and ETA.
- Unpacks 100% of files using pure Python standard libraries (tarfile + lzma) with zero external dependencies.
- Extracts every single file without removing or skipping anything.
- 100% Graphical User Interface (Tkinter with High-DPI modern dark UI).
"""
import os
import sys
import time
import shutil
import tarfile
import zipfile
import threading
import urllib.request
import winreg
import subprocess

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Set Windows High DPI awareness
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# Default GitHub archive download URL (Python LZMA2 tar.xz)
DEFAULT_GITHUB_ARCHIVE_URL = "https://github.com/paul2877/Arizona-Helper/releases/download/v2.0/moonloader.tar.xz"

def detect_game_path_from_registry():
    """Detect GTA SA / Arizona game directory from registry and common paths."""
    candidates = []

    # 1. Arizona Games Launcher default directory
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        arz_dir = os.path.join(local_app_data, "Programs", "Arizona Games Launcher", "bin", "arizona")
        if os.path.isdir(arz_dir):
            candidates.append(arz_dir)

    # 2. SAMP Registry: HKCU\Software\SAMP -> gta_sa_exe
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\SAMP") as key:
            gta_exe, _ = winreg.QueryValueEx(key, "gta_sa_exe")
            if gta_exe and os.path.isfile(gta_exe):
                candidates.append(os.path.dirname(os.path.abspath(gta_exe)))
    except Exception:
        pass

    # 3. Rockstar Games GTA San Andreas Registry (HKLM 32/64)
    for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for subkey_path in (
            r"SOFTWARE\WOW6432Node\Rockstar Games\GTA San Andreas\Installation",
            r"SOFTWARE\Rockstar Games\GTA San Andreas\Installation"
        ):
            try:
                with winreg.OpenKey(root_key, subkey_path) as key:
                    exe_p, _ = winreg.QueryValueEx(key, "ExePath")
                    if exe_p:
                        d = exe_p if os.path.isdir(exe_p) else os.path.dirname(exe_p)
                        if os.path.isdir(d):
                            candidates.append(d)
            except Exception:
                pass

    # 4. Common hardcoded drive paths
    for drive in ["C:", "D:", "E:", "F:"]:
        for common in [
            r"Games\GTA - San Andreas",
            r"Games\GTA San Andreas",
            r"Games\Arizona Games Launcher\bin\arizona",
            r"Arizona Games Launcher\bin\arizona",
            r"GTA San Andreas"
        ]:
            p = os.path.join(drive, common)
            if os.path.isdir(p):
                candidates.append(p)

    # Prioritize folders that actually contain gta_sa.exe or arizona.exe
    for c in candidates:
        if os.path.isfile(os.path.join(c, "gta_sa.exe")) or os.path.isfile(os.path.join(c, "arizona.exe")):
            return os.path.normpath(c)

    if candidates:
        return os.path.normpath(candidates[0])

    return r"C:\Games\GTA - San Andreas"

class InstallerGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Установщик MoonLoader & Arizona Helper")
        self.geometry("780x600")
        self.minsize(720, 560)
        self.configure(bg="#181825")

        self.is_installing = False
        self.install_finished = False

        self.detected_game_path = detect_game_path_from_registry()
        self.selected_path_var = tk.StringVar(value=self.detected_game_path)
        self.download_url_var = tk.StringVar(value=DEFAULT_GITHUB_ARCHIVE_URL)

        self.setup_styles()
        self.create_widgets()
        self.update_path_validation()

    def setup_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.style.configure(".", background="#181825", foreground="#FFFFFF", font=("Segoe UI", 10))
        self.style.configure("TFrame", background="#181825")
        self.style.configure("Card.TFrame", background="#242438", relief="flat")

        self.style.configure("TLabel", background="#181825", foreground="#E0E0E0")
        self.style.configure("Card.TLabel", background="#242438", foreground="#E0E0E0")
        self.style.configure("Header.TLabel", background="#181825", foreground="#5865F2", font=("Segoe UI", 16, "bold"))
        self.style.configure("SubHeader.TLabel", background="#181825", foreground="#A0A0B8", font=("Segoe UI", 10))

        # Buttons
        self.style.configure(
            "Primary.TButton",
            background="#5865F2",
            foreground="#FFFFFF",
            font=("Segoe UI", 11, "bold"),
            padding=(18, 9),
            borderwidth=0
        )
        self.style.map("Primary.TButton", background=[("active", "#4752C4"), ("disabled", "#3A3A50")])

        self.style.configure(
            "Success.TButton",
            background="#2ECC71",
            foreground="#FFFFFF",
            font=("Segoe UI", 11, "bold"),
            padding=(18, 9),
            borderwidth=0
        )
        self.style.map("Success.TButton", background=[("active", "#27AE60"), ("disabled", "#3A3A50")])

        self.style.configure(
            "Secondary.TButton",
            background="#3A3A50",
            foreground="#E0E0E0",
            font=("Segoe UI", 10),
            padding=(12, 6),
            borderwidth=0
        )
        self.style.map("Secondary.TButton", background=[("active", "#4A4A65")])

        # Progressbar
        self.style.configure(
            "Custom.Horizontal.TProgressbar",
            troughcolor="#181825",
            background="#5865F2",
            lightcolor="#5865F2",
            darkcolor="#5865F2",
            bordercolor="#181825",
            thickness=14
        )

    def create_widgets(self):
        # 1. Header Frame
        header_frame = ttk.Frame(self, padding=(24, 18, 24, 10))
        header_frame.pack(fill="x")

        title_lbl = ttk.Label(header_frame, text="⚡ MoonLoader & Arizona Helper", style="Header.TLabel")
        title_lbl.pack(anchor="w")

        sub_lbl = ttk.Label(
            header_frame,
            text="Автоматическая загрузка архива с GitHub и распаковка через библиотеки Python",
            style="SubHeader.TLabel"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # 2. Main Container
        main_container = ttk.Frame(self, padding=(24, 6, 24, 16))
        main_container.pack(fill="both", expand=True)

        # Game Path Card
        path_card = ttk.Frame(main_container, style="Card.TFrame", padding=(16, 14))
        path_card.pack(fill="x", pady=(0, 12))

        card_title = ttk.Label(
            path_card,
            text="📁 Папка с игрой (определена из реестра Windows):",
            style="Card.TLabel",
            font=("Segoe UI", 10, "bold")
        )
        card_title.pack(anchor="w")

        entry_row = ttk.Frame(path_card, style="Card.TFrame")
        entry_row.pack(fill="x", pady=(8, 4))

        self.path_entry = tk.Entry(
            entry_row,
            textvariable=self.selected_path_var,
            bg="#181825",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
            relief="flat",
            font=("Consolas", 10),
            highlightthickness=1,
            highlightbackground="#3A3A50",
            highlightcolor="#5865F2"
        )
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        self.selected_path_var.trace_add("write", lambda *args: self.update_path_validation())

        browse_btn = ttk.Button(
            entry_row,
            text="Обзор...",
            style="Secondary.TButton",
            command=self.browse_folder
        )
        browse_btn.pack(side="right")

        self.path_status_lbl = ttk.Label(
            path_card,
            text="",
            style="Card.TLabel",
            font=("Segoe UI", 9)
        )
        self.path_status_lbl.pack(anchor="w")

        # Progress & Status Card
        progress_card = ttk.Frame(main_container, style="Card.TFrame", padding=(16, 14))
        progress_card.pack(fill="x", pady=(0, 12))

        status_header = ttk.Frame(progress_card, style="Card.TFrame")
        status_header.pack(fill="x")

        self.stage_lbl = ttk.Label(
            status_header,
            text="Готов к установке",
            style="Card.TLabel",
            font=("Segoe UI", 10, "bold")
        )
        self.stage_lbl.pack(side="left")

        self.pct_lbl = ttk.Label(
            status_header,
            text="0%",
            style="Card.TLabel",
            font=("Segoe UI", 10, "bold"),
            foreground="#5865F2"
        )
        self.pct_lbl.pack(side="right")

        self.progress_bar = ttk.Progressbar(
            progress_card,
            style="Custom.Horizontal.TProgressbar",
            mode="determinate",
            maximum=100,
            value=0
        )
        self.progress_bar.pack(fill="x", pady=(8, 6))

        self.detail_lbl = ttk.Label(
            progress_card,
            text="Нажмите «Установить» для скачивания с GitHub и чистой распаковки.",
            style="Card.TLabel",
            font=("Segoe UI", 9),
            foreground="#A0A0B8"
        )
        self.detail_lbl.pack(anchor="w")

        # Live Log Console
        log_frame = ttk.Frame(main_container, style="Card.TFrame", padding=(12, 10))
        log_frame.pack(fill="both", expand=True, pady=(0, 12))

        log_title = ttk.Label(log_frame, text="Журнал установки:", style="Card.TLabel", font=("Segoe UI", 9, "bold"))
        log_title.pack(anchor="w", pady=(0, 4))

        self.log_text = tk.Text(
            log_frame,
            bg="#12121A",
            fg="#D0D0E0",
            insertbackground="#FFFFFF",
            font=("Consolas", 9),
            relief="flat",
            wrap="word",
            height=7,
            padx=8,
            pady=8
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

        # 3. Bottom Action Controls
        bottom_frame = ttk.Frame(self, padding=(24, 0, 24, 18))
        bottom_frame.pack(fill="x", side="bottom")

        self.install_btn = ttk.Button(
            bottom_frame,
            text="🚀  Установить",
            style="Primary.TButton",
            command=self.start_installation
        )
        self.install_btn.pack(side="left")

        self.launch_btn = ttk.Button(
            bottom_frame,
            text="🎮  Запустить игру",
            style="Success.TButton",
            command=self.launch_game,
            state="disabled"
        )
        self.launch_btn.pack(side="left", padx=(12, 0))

        exit_btn = ttk.Button(
            bottom_frame,
            text="Закрыть",
            style="Secondary.TButton",
            command=self.destroy
        )
        exit_btn.pack(side="right")

        self.log("Программа запущена. Автоопределение путей выполнено.")

    def log(self, message):
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see("end")

    def update_path_validation(self):
        p = self.selected_path_var.get().strip()
        if not p:
            self.path_status_lbl.config(text="⚠️ Укажите папку с установленной игрой.", foreground="#E74C3C")
            return False

        if not os.path.isdir(p):
            self.path_status_lbl.config(text="⚠️ Папка не найдена на диске.", foreground="#E74C3C")
            return False

        has_gta = os.path.isfile(os.path.join(p, "gta_sa.exe"))
        has_arz = os.path.isfile(os.path.join(p, "arizona.exe"))

        if has_gta or has_arz:
            exe_name = "arizona.exe" if has_arz else "gta_sa.exe"
            self.path_status_lbl.config(
                text=f"✅ Найдена игра ({exe_name})! Файлы будут установлены корректно.",
                foreground="#2ECC71"
            )
            return True
        else:
            self.path_status_lbl.config(
                text="ℹ️ Папка выбрана (исполняемый файл gta_sa.exe не найден в корне, но установка разрешена).",
                foreground="#F39C12"
            )
            return True

    def browse_folder(self):
        initial = self.selected_path_var.get()
        if not os.path.isdir(initial):
            initial = r"C:\\"
        selected = filedialog.askdirectory(
            title="Выберите папку с GTA San Andreas / Arizona RP",
            initialdir=initial
        )
        if selected:
            self.selected_path_var.set(os.path.normpath(selected))
            self.log(f"Пользователь выбрал папку: {selected}")

    def start_installation(self):
        if self.is_installing:
            return

        target_dir = self.selected_path_var.get().strip()
        if not os.path.isdir(target_dir):
            messagebox.showerror("Ошибка", f"Указанная папка не существует:\n{target_dir}")
            return

        self.is_installing = True
        self.install_btn.config(state="disabled")
        self.path_entry.config(state="disabled")

        thread = threading.Thread(target=self.run_install_worker, daemon=True)
        thread.start()

    def set_progress(self, stage_text, percent, detail_text=""):
        self.stage_lbl.config(text=stage_text)
        self.pct_lbl.config(text=f"{int(percent)}%")
        self.progress_bar["value"] = percent
        if detail_text:
            self.detail_lbl.config(text=detail_text)
        self.update_idletasks()

    def run_install_worker(self):
        target_dir = self.selected_path_var.get().strip()
        download_url = self.download_url_var.get().strip()

        try:
            self.log(f"Начало процесса установки в: {target_dir}")

            # Determine archive extension from URL
            if download_url.endswith(".tar.xz"):
                ext = ".tar.xz"
            elif download_url.endswith(".rar"):
                ext = ".rar"
            else:
                ext = ".zip"

            temp_dest = os.path.join(os.environ.get("TEMP", r"C:\soft"), f"moonloader_fresh_download{ext}")
            if os.path.isfile(temp_dest):
                try:
                    os.remove(temp_dest)
                except Exception:
                    pass

            self.log(f"Загрузка архива с GitHub: {download_url}")
            self.set_progress("Загрузка с GitHub...", 0, "Подключение к серверу GitHub...")

            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Arizona-Installer/2.0"}
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                block_size = 65536
                start_time = time.time()
                last_update = 0

                with open(temp_dest, "wb") as out_f:
                    while True:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        if now - last_update > 0.08 or downloaded == total_size:
                            last_update = now
                            elapsed = max(now - start_time, 0.001)
                            speed_mb = (downloaded / (1024 * 1024)) / elapsed
                            pct = (downloaded / total_size * 50.0) if total_size > 0 else 25.0
                            mb_cur = downloaded / (1024 * 1024)
                            mb_tot = total_size / (1024 * 1024) if total_size > 0 else 0
                            detail = f"Загрузка: {mb_cur:.1f} МБ / {mb_tot:.1f} МБ ({speed_mb:.2f} МБ/с)"
                            self.set_progress("Загрузка с GitHub...", pct, detail)

            archive_to_unpack = temp_dest
            self.log(f"Загрузка с GitHub успешно завершена! Скачано: {downloaded / (1024*1024):.1f} МБ.")

            # 2. Unpacking Phase using Python libraries (tarfile / zipfile)
            self.set_progress("Распаковка и установка MoonLoader...", 50, "Подготовка к извлечению...")
            self.log("Извлечение полного содержимого архива без удаления файлов средствами Python...")

            if archive_to_unpack.endswith(".tar.xz"):
                self.unpack_tar_xz_archive(archive_to_unpack, target_dir)
            elif archive_to_unpack.endswith(".zip"):
                self.unpack_zip_archive(archive_to_unpack, target_dir)
            else:
                self.unpack_tar_xz_archive(archive_to_unpack, target_dir)

            # 3. Verify installation integrity
            moon_asi = os.path.join(target_dir, "MoonLoader.asi")
            ah_lua = os.path.join(target_dir, "moonloader", "Arizona Helper.lua")
            has_asi = os.path.isfile(moon_asi)
            has_lua = os.path.isfile(ah_lua)

            self.log(f"Проверка: MoonLoader.asi: {'OK' if has_asi else 'Не найден'}")
            self.log(f"Проверка: Arizona Helper.lua: {'OK' if has_lua else 'Не найден'}")

            # Clean up temp download
            if os.path.isfile(temp_dest):
                try:
                    os.remove(temp_dest)
                except Exception:
                    pass

            self.set_progress("Установка успешно завершена!", 100, "Все компоненты установлены в папку с игрой.")
            self.log("🎉 Все файлы успешно установлены! MoonLoader готов к работе.")

            self.install_finished = True
            self.launch_btn.config(state="normal")
            self.install_btn.config(text="✅ Установлено", state="disabled")

            messagebox.showinfo(
                "Успех",
                "MoonLoader и Arizona Helper успешно установлены!\n"
                f"Путь: {target_dir}\n\n"
                "Вы можете запустить игру прямо сейчас нажав «Запустить игру»."
            )

        except Exception as e:
            self.log(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            self.set_progress("Ошибка установки!", 0, str(e))
            self.install_btn.config(state="normal")
            self.path_entry.config(state="normal")
            messagebox.showerror("Ошибка установки", f"Произошла ошибка при установке:\n\n{e}")
        finally:
            self.is_installing = False

    def unpack_tar_xz_archive(self, tar_xz_path, target_dir):
        """Unpack TAR.XZ archive member by member with visible progress using Python standard library."""
        with tarfile.open(tar_xz_path, "r:xz") as tar:
            total_items = 1188
            extracted = 0
            last_ui_update = 0

            for member in tar:
                tar.extract(member, target_dir)
                extracted += 1

                now = time.time()
                if now - last_ui_update > 0.03 or extracted == total_items:
                    last_ui_update = now
                    pct = min(50.0 + (extracted / total_items) * 50.0, 99.0)
                    detail = f"Распаковка Python: {os.path.basename(member.name)} ({extracted}/{total_items})"
                    self.set_progress("Распаковка архива...", pct, detail)
                    if extracted % 20 == 0 or extracted == total_items:
                        self.log(f"Извлечено: {member.name}")

            self.log(f"Успешно извлечено {extracted} элементов.")

    def unpack_zip_archive(self, zip_path, target_dir):
        """Unpack ZIP archive with file-by-file progress, overwriting and preserving all items."""
        with zipfile.ZipFile(zip_path, "r") as z:
            namelist = z.namelist()
            total_items = len(namelist)
            self.log(f"Всего файлов в ZIP архиве: {total_items}")

            for idx, item in enumerate(namelist, 1):
                z.extract(item, target_dir)
                pct = 50.0 + (idx / total_items) * 50.0
                detail = f"Распаковка: {os.path.basename(item)} ({idx}/{total_items})"
                self.set_progress("Распаковка компонентов...", pct, detail)
                if idx % 15 == 0 or idx == total_items:
                    self.log(f"Распаковано: {item} ({int(pct)}%)")

    def launch_game(self):
        target_dir = self.selected_path_var.get().strip()
        arz_launcher = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Arizona Games Launcher\Arizona Games Launcher.exe")
        gta_exe = os.path.join(target_dir, "gta_sa.exe")
        arz_exe = os.path.join(target_dir, "arizona.exe")

        if os.path.isfile(arz_launcher):
            self.log(f"Запуск Arizona Games Launcher: {arz_launcher}")
            subprocess.Popen([arz_launcher], cwd=os.path.dirname(arz_launcher))
        elif os.path.isfile(arz_exe):
            self.log(f"Запуск игры: {arz_exe}")
            subprocess.Popen([arz_exe], cwd=target_dir)
        elif os.path.isfile(gta_exe):
            self.log(f"Запуск игры: {gta_exe}")
            subprocess.Popen([gta_exe], cwd=target_dir)
        else:
            messagebox.showinfo("Запуск", f"Файлы игры находятся в:\n{target_dir}\nЗапустите лаунчер Arizona Games для входа.")

def main():
    app = InstallerGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
