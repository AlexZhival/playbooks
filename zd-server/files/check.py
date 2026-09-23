#!/usr/bin/env python3
"""
Проверка, что служебные аккаунты Google заведены и документы им расшарены.

Запуск:
    python3 check.py                      проверит все файлы ключей в текущей папке
    python3 check.py brain-founders.json  проверит один файл

Ничего не меняет и никуда не пишет: только читает и показывает отчет.
Если не хватает библиотек, выполните:
    pip3 install --break-system-packages google-auth requests
(на обычном компьютере тот же список, но без --break-system-packages)
"""
import glob
import json
import os
import sys

try:
    import requests
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
except ImportError:
    sys.exit("Не хватает библиотек. Выполните:\n"
             "  pip3 install --break-system-packages google-auth requests")

DRIVE = "https://www.googleapis.com/drive/v3/files"
SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly",
          "https://www.googleapis.com/auth/spreadsheets.readonly"]

OK, NO, WARN = "  [есть]   ", "  [НЕТ]   ", "  [!]     "


def human(mime):
    return {
        "application/vnd.google-apps.spreadsheet": "Google Таблица",
        "application/vnd.google-apps.document": "Google Документ",
        "application/vnd.google-apps.presentation": "Google Презентация",
        "application/vnd.google-apps.folder": "папка",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint",
    }.get(mime, "другое")


def check_one(path):
    print("\n" + "=" * 64)
    print("ФАЙЛ КЛЮЧА:", os.path.basename(path))
    print("=" * 64)
    problems = []

    # 1. файл ключа
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(NO + "файл не читается как JSON:", e)
        return ["файл ключа битый: " + os.path.basename(path)]
    if raw.get("type") != "service_account" or not raw.get("client_email"):
        print(NO + "это не ключ служебного аккаунта")
        return ["не тот файл: " + os.path.basename(path)]
    print(OK + "это ключ служебного аккаунта")
    print("          адрес:", raw["client_email"])
    print("          проект:", raw.get("project_id", "не указан"))

    # 2. ключ действующий
    try:
        creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
        creds.refresh(Request())
        head = {"Authorization": "Bearer " + creds.token}
        print(OK + "Google принял ключ, он действующий")
    except Exception as e:
        print(NO + "Google не принял ключ:", str(e)[:160])
        return ["ключ не работает: " + raw["client_email"] + ". Возможно, он удален или отозван"]

    # 3. Drive API
    try:
        r = requests.get(DRIVE, headers=head, timeout=40, params={
            "pageSize": 1000, "q": "trashed=false",
            "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
            "fields": "files(id,name,mimeType)"})
    except Exception as e:
        print(NO + "нет связи с Google:", e)
        return ["нет связи с Google"]
    if r.status_code == 403 and "accessNotConfigured" in r.text:
        print(NO + "Google Drive API не включен в проекте")
        return ["включить Google Drive API в проекте " + str(raw.get("project_id"))]
    if r.status_code != 200:
        print(NO + "Drive ответил", r.status_code, r.text[:120])
        return ["Drive отвечает ошибкой " + str(r.status_code)]
    print(OK + "Google Drive API включен")

    files = r.json().get("files", [])
    by_kind = {}
    for f in files:
        by_kind[human(f["mimeType"])] = by_kind.get(human(f["mimeType"]), 0) + 1

    # 4. расшарены ли документы
    if not files:
        print(NO + "роботу не расшарен ни один документ")
        problems.append("расшарить документы на адрес " + raw["client_email"])
    else:
        print(OK + f"роботу видно объектов: {len(files)}")
        for k, v in sorted(by_kind.items(), key=lambda x: -x[1]):
            print(f"          {v:4}  {k}")

    # 5. Sheets API
    sheet = next((f for f in files if f["mimeType"].endswith("apps.spreadsheet")), None)
    if not sheet:
        print(WARN + "не на чем проверить Sheets API: таблиц роботу не видно")
    else:
        rs = requests.get(f"{SHEETS}/{sheet['id']}", headers=head, timeout=40,
                          params={"fields": "sheets.properties.title"})
        if rs.status_code == 200:
            tabs = [x["properties"]["title"] for x in rs.json().get("sheets", [])]
            print(OK + f"Google Sheets API включен, таблицы читаются по вкладкам")
            print(f"          проверено на «{sheet['name'][:40]}», вкладок: {len(tabs)}")
        elif rs.status_code == 403 and "accessNotConfigured" in rs.text:
            print(NO + "Google Sheets API не включен в проекте")
            problems.append("включить Google Sheets API в проекте " + str(raw.get("project_id")))
        else:
            print(NO + "Sheets ответил", rs.status_code)
            problems.append("Sheets отвечает ошибкой " + str(rs.status_code))

    # 6. чтение документа
    doc = next((f for f in files if f["mimeType"].endswith("apps.document")), None)
    if doc:
        rd = requests.get(f"{DRIVE}/{doc['id']}/export", headers=head, timeout=60,
                          params={"mimeType": "text/plain"})
        if rd.status_code == 200 and len(rd.content) > 0:
            print(OK + f"документы открываются, проверено на «{doc['name'][:40]}»")
        else:
            print(NO + "документ не открылся, код " + str(rd.status_code))
            problems.append("документы не открываются на чтение")

    # 7. права: только чтение
    scopes_ok = all("readonly" in s for s in SCOPES)
    print(OK + "запрошены права только на чтение" if scopes_ok else WARN + "проверьте права")
    return problems


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    paths = args or sorted(glob.glob("*.json"))
    paths = [p for p in paths if os.path.isfile(p)]
    if not paths:
        sys.exit("Не нашел файлов ключей. Положите скачанные JSON рядом со скриптом\n"
                 "или укажите путь: python3 check.py путь/к/ключу.json")

    print("Проверяю служебные аккаунты Google. Ничего не меняю, только читаю.")
    all_problems = []
    checked = 0
    for p in paths:
        try:
            if json.load(open(p, encoding="utf-8")).get("type") != "service_account":
                continue
        except Exception:
            continue
        checked += 1
        all_problems += check_one(p)

    print("\n" + "=" * 64)
    if not checked:
        print("ИТОГ: не нашел ни одного ключа служебного аккаунта.")
        print("Скачайте ключи из Google Cloud: вкладка Keys, Add Key, Create new key, JSON.")
    elif not all_problems:
        print(f"ИТОГ: проверено ключей {checked}, все в порядке.")
        print("Можно переходить к развертыванию сервера.")
    else:
        print(f"ИТОГ: проверено ключей {checked}, есть что поправить:")
        for i, p in enumerate(all_problems, 1):
            print(f"  {i}. {p}")
    print("=" * 64)


if __name__ == "__main__":
    main()
