# -*- coding: utf-8 -*-
"""
Desktop File Points Extractor using Task Points AI Model.
Extracts task categories and points from raw/garbage text files on the desktop.
"""
import os
import sys
import re
import glob

# Ensure UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, r"C:\soft\Arizona-Helper-Repo")
try:
    from task_ai_engine import predict_task_and_points, load_task_ai
except ImportError:
    print("[!] Ошибка: task_ai_engine.py не найден в C:\\soft\\Arizona-Helper-Repo!")
    input("Нажмите Enter...")
    sys.exit(1)

def get_desktop_dir():
    return os.path.expanduser(r"~\Desktop")

def find_desktop_txt_files():
    desktop = get_desktop_dir()
    found = []
    # Direct txt on desktop
    for f in glob.glob(os.path.join(desktop, "*.txt")):
        if os.path.isfile(f) and not os.path.basename(f).startswith("РЕЗУЛЬТАТ"):
            found.append(f)
    # Txt in subfolders of desktop
    for f in glob.glob(os.path.join(desktop, "*", "*.txt")):
        if os.path.isfile(f) and not os.path.basename(f).startswith("РЕЗУЛЬТАТ"):
            found.append(f)
    return found

def clean_file_bytes(raw_bytes):
    for enc in ["utf-8-sig", "utf-8", "cp1251", "utf-16", "latin1"]:
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")

def extract_points_from_file(filepath):
    filepath = filepath.strip("\"'")
    if not os.path.isfile(filepath):
        print(f"\n[!] Файл не найден: {filepath}")
        return

    print("=" * 72)
    print(f"📂 АНАЛИЗ ФАЙЛА: {os.path.basename(filepath)}")
    print(f"📍 Путь: {filepath}")
    print("=" * 72)

    try:
        with open(filepath, "rb") as f:
            raw = f.read()
    except Exception as e:
        print(f"[!] Ошибка чтения файла: {e}")
        return

    text = clean_file_bytes(raw)
    # Strip BB-codes [FONT...], [URL...], [/URL], [B], [CENTER], etc.
    clean_text = re.sub(r'\[/?[^\]]+\]', ' ', text)
    lines = clean_text.splitlines()

    print(f"Строк в файле: {len(lines)}. Запуск нейросети для извлечения заданий и баллов...\n")

    detected_items = []
    task_groups = {} # task_name -> {"points_each": int, "count": int, "total": int, "lines": []}
    grand_total_points = 0

    # Words to ignore (metadata/headers)
    ignore_headers = [
        "руководству", "шерифу", "от сотрудника", "заявление на повышение",
        "паспорт", "showpass", "wbook", "jobprogress", "discord", "спец. рация",
        "https://", "http://", "imgur.com", "ibb.co"
    ]

    for line in lines:
        s = line.strip()
        if not s or len(s) < 3:
            continue

        lower = s.lower()
        if any(h in lower for h in ignore_headers) and not any(k in lower for k in ["штраф", "арест", "завод", "патрул", "поручен", "лекци", "трениров", "допрос", "блок"]):
            continue

        # AI prediction
        res = predict_task_and_points(s)
        pts = res["points"]
        task_name = res["task"]
        conf = res["confidence"]

        # Only count if AI identified a real task (not trash/noise)
        if pts > 0 and conf >= 50.0:
            detected_items.append((s, task_name, pts, conf))
            grand_total_points += pts

            if task_name not in task_groups:
                task_groups[task_name] = {
                    "points_each": pts,
                    "count": 0,
                    "total": 0,
                    "lines": []
                }
            task_groups[task_name]["count"] += 1
            task_groups[task_name]["total"] += pts
            task_groups[task_name]["lines"].append((s, conf))

    # Output Summary Table
    print("=" * 72)
    print("                РЕЗУЛЬТАТЫ ИЗВЛЕЧЕНИЯ БАЛЛОВ (AI)")
    print("=" * 72)
    print(f"{'Категория выполненного задания':<38} | {'Кол-во':<7} | {'Начислено'}")
    print("-" * 72)

    for task_name, data in sorted(task_groups.items(), key=lambda x: x[1]["total"], reverse=True):
        print(f"• {task_name:<36} | {data['count']:<7} | +{data['total']} б. ({data['points_each']} б./шт.)")

    print("-" * 72)
    print(f"🏆 ВСЕГО НАБРАНО БАЛЛОВ: [ {grand_total_points} БАЛЛОВ ] (Заданий: {len(detected_items)})")
    print("=" * 72)

    # Save detailed report to Desktop
    desktop = get_desktop_dir()
    out_file = os.path.join(desktop, "РЕЗУЛЬТАТ_ИЗВЛЕЧЕНИЯ_БАЛЛОВ.txt")
    try:
        with open(out_file, "w", encoding="utf-8") as out:
            out.write("=" * 72 + "\n")
            out.write("     ВЕДОМОСТЬ НАЧИСЛЕНИЯ БАЛЛОВ (ARIZONA RP // AI EXTRACTOR)\n")
            out.write(f"     Исходный файл : {os.path.basename(filepath)}\n")
            out.write(f"     Всего заданий  : {len(detected_items)}\n")
            out.write(f"     ИТОГО БАЛЛОВ   : {grand_total_points} БАЛЛОВ\n")
            out.write("=" * 72 + "\n\n")

            out.write("СВОДНАЯ СТАТИСТИКА ПО ЗАДАНИЯМ:\n")
            out.write("-" * 72 + "\n")
            for task_name, data in sorted(task_groups.items(), key=lambda x: x[1]["total"], reverse=True):
                out.write(f"• {task_name:<40} : {data['count']} раз(а) -> +{data['total']} баллов\n")
            out.write("-" * 72 + "\n\n")

            out.write("ДЕТАЛИЗАЦИЯ ИЗВЛЕЧЕННЫХ СТРОК ИЗ МУСОРА:\n")
            out.write("-" * 72 + "\n")
            for line_str, t_name, p, c in detected_items:
                out.write(f"[+{p:2d} б.] [{t_name}] (уверенность {c:.1f}%)\n")
                out.write(f"       Цитата: \"{line_str}\"\n\n")

        print(f"\n💾 Полный отчет с деталями сохранен на рабочий стол:\n   {out_file}\n")
    except Exception as e:
        print(f"[!] Не удалось записать файл отчета: {e}")

def main():
    weights = load_task_ai()
    acc = weights.get("accuracy", "99.8%") if weights else "?"

    print("=" * 72)
    print("   🤖 ARIZONA RP // AI ИЗВЛЕЧЕНИЕ БАЛЛОВ ИЗ ТЕКСТОВОГО ФАЙЛА")
    print(f"   Модель: task_ai_weights.json | Точность: {acc}")
    print("=" * 72)

    # 1. If file was dragged onto .bat or passed via argument
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1].strip("\"'")):
        extract_points_from_file(sys.argv[1].strip("\"'"))
        input("\nНажмите Enter для завершения...")
        return

    # 2. Check desktop files automatically
    desktop_files = find_desktop_txt_files()

    print("\nНайденные текстовые файлы на рабочем столе:")
    if desktop_files:
        for idx, f in enumerate(desktop_files[:9], 1):
            rel = os.path.relpath(f, get_desktop_dir())
            print(f"  [{idx}] {rel} ({os.path.getsize(f)} байт)")
    else:
        print("  (на рабочем столе нет .txt файлов)")

    print("\nВарианты:")
    if desktop_files:
        print(f"  [1..{len(desktop_files[:9])}] Выбрать файл из списка выше")
    print("  [0] Перетащить любой файл сюда / ввести путь вручную")
    print("  [q] Выход")

    while True:
        try:
            print("\n👉 Ваш выбор: ", end="", flush=True)
            choice = sys.stdin.readline()
            if not choice:
                break
            choice = choice.strip().strip("\"'")

            if choice.lower() in ["q", "exit", "quit", "выход"]:
                break

            if choice.isdigit():
                num = int(choice)
                if 1 <= num <= len(desktop_files[:9]):
                    extract_points_from_file(desktop_files[num - 1])
                    break
                elif num == 0:
                    print("📁 Введите путь к файлу (или перетащите его в это окно): ", end="", flush=True)
                    p = sys.stdin.readline()
                    if p and os.path.isfile(p.strip().strip("\"'")):
                        extract_points_from_file(p.strip().strip("\"'"))
                        break
                    else:
                        print("[!] Файл не найден!")
                else:
                    print("[!] Неверный номер.")
            elif os.path.isfile(choice):
                extract_points_from_file(choice)
                break
            else:
                print("[!] Файл не найден. Попробуйте снова.")
        except KeyboardInterrupt:
            break

    input("\nНажмите Enter для закрытия окна...")

if __name__ == "__main__":
    main()
