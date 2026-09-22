#!/usr/bin/env python3
"""
Каталог источников компании из Штаба.

  python3 catalog.py                 весь каталог текстом (папки, источники, связи)
  python3 catalog.py --json          то же в JSON
  python3 catalog.py найти <слово>   источники, где встречается слово
  python3 catalog.py папка <id>      что лежит в папке

Ключ мозга берется из файла .brainkey рядом со скриптом мозга
(переменная BRAIN_KEY) - он определяет, какие папки видно.
"""
import os, sys, json, urllib.request

BASE = os.environ.get("HUB_URL", "https://zavod-aplayers.zhivotov-alexander.workers.dev")

def key():
    k = os.environ.get("BRAIN_KEY", "").strip()
    if k: return k
    for p in (os.path.expanduser("~/.aplayers/brainkey"),
              os.path.expanduser("~/.aplayers/brainkey")):
        if os.path.exists(p):
            return open(p).read().strip()
    sys.exit("Нет ключа мозга. Положите его в .brainkey рядом со скриптом.")

def fetch(path):
    # Cloudflare отбивает запросы без человеческого User-Agent кодом 1010
    req = urllib.request.Request(BASE + path, headers={
        "x-brain-key": key(),
        "user-agent": "ZD-Brain/1.0 (+catalog reader)",
        "accept": "*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        sys.exit(f"Штаб ответил {e.code}: {e.read().decode('utf-8')[:200]}")

def main():
    a = sys.argv[1:]
    if a and a[0] == "--json":
        print(fetch("/api/v1/catalog")); return
    if a and a[0] in ("найти", "find") and len(a) > 1:
        d = json.loads(fetch("/api/v1/catalog")); q = " ".join(a[1:]).lower()
        hits = [s for s in d["sources"]
                if q in (s["title"] + " " + s["about"] + " " + s["folder_title"]).lower()]
        if not hits: print("Ничего не нашлось. Папки, которые мне видны:",
                           ", ".join(f["title"] for f in d["folders"])); return
        for s in hits:
            print(f"\n{s['title']}{'  (источник правды)' if s['source_of_truth'] else ''}")
            print(f"  папка: {s['folder_title']} | {s['kind']} | ведет: {s['owner']} | обновляется: {s['updated']}")
            if s["about"]: print(f"  {s['about']}")
            if s["url"]: print(f"  ссылка: {s['url']}")
            if s["links"]: print(f"  связано с: {', '.join(s['links'])}")
        return
    if a and a[0] == "папка" and len(a) > 1:
        d = json.loads(fetch("/api/v1/catalog"))
        fid = a[1]
        for s in d["sources"]:
            if s["folder"] == fid:
                print(f"- {s['title']}{'  (источник правды)' if s['source_of_truth'] else ''}: {s['url']}")
        return
    print(fetch("/api/v1/catalog.md"))

if __name__ == "__main__":
    main()
