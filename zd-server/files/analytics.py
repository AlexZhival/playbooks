#!/usr/bin/env python3
"""
Аналитика компании: витрины ClickHouse, только чтение.

  python3 analytics.py таблицы                    список витрин
  python3 analytics.py колонки <таблица>          поля витрины
  python3 analytics.py "<SQL>"                    произвольный SELECT
  python3 analytics.py воронка [месяцев]          деньги и оплаты по месяцам
  python3 analytics.py телефония [месяцев]        звонки, дозвон, минуты
  python3 analytics.py очередь                    открытые сделки без касания

ПРАВИЛА, без которых цифры врут:
- деньги считаем sum(received_money) по payment_at, не payed_money и не cost_money;
- cycle_type делит циклы на «С платным заказом» и «Бесплатные заказы»,
  поэтому конверсия по всем циклам вместе бессмысленна;
- у оплативших ранние этапы проставлены backfill-ом;
- менеджер CRM и менеджер АТС это разные справочники, их нельзя склеивать;
- период 2026, календарь Europe/Moscow;
- писать в базу нельзя ничем и никогда.
"""
import os, sys, requests, urllib3
urllib3.disable_warnings()

ENV = os.environ.get("CH_ENV", os.path.expanduser("~/.aplayers/clickhouse.env"))

def creds():
    if not os.path.exists(ENV):
        sys.exit(f"Нет файла кред: {ENV}")
    d = {}
    for line in open(ENV, encoding="utf-8").read().splitlines():
        line = line.strip()                      # файл бывает с виндовыми переводами строк
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); d[k.strip()] = v.strip()
    return d

def q(sql):
    c = creds()
    r = requests.post(f"https://{c['CLICKHOUSE_HOST']}:{c['CLICKHOUSE_PORT']}/",
                      auth=(c["CLICKHOUSE_USER"], c["CLICKHOUSE_PASSWORD"]),
                      data=sql.encode("utf-8"), verify=False, timeout=90)
    if r.status_code != 200:
        sys.exit(f"ClickHouse ответил {r.status_code}: {r.text[:400]}")
    return r.text

def guard(sql):
    bad = ("insert", "alter", "drop", "create", "truncate", "delete", "update", "rename", "attach", "grant")
    low = sql.lower()
    if any(low.strip().startswith(b) or f" {b} " in low for b in bad):
        sys.exit("Это запись в базу. Второй мозг читает аналитику и ничего в нее не пишет.")
    return sql

PRESETS = {
 "воронка": lambda n: f"""SELECT toStartOfMonth(toTimeZone(payment_at,'Europe/Moscow')) AS mesyac,
   count() AS oplat, round(sum(received_money)/1000000,2) AS mln_rub, round(avg(received_money)) AS sredniy_chek
   FROM data_marts.dm__sales_funnel_cycles
   WHERE payment_at >= addMonths(toStartOfMonth(now()), -{n}) GROUP BY mesyac ORDER BY mesyac FORMAT TSVWithNames""",
 "телефония": lambda n: f"""SELECT toStartOfMonth(call_date) AS mesyac, count(DISTINCT manager) AS mopov,
   sum(calls_cnt) AS zvonkov, round(100*sum(connected_cnt)/sum(calls_cnt),1) AS dozvon_pct,
   round(sum(talk_minutes)) AS minut
   FROM data_marts.dm__telephony_manager_days
   WHERE call_date >= addMonths(toStartOfMonth(now()), -{n}) GROUP BY mesyac ORDER BY mesyac FORMAT TSVWithNames""",
 "очередь": lambda n: """SELECT multiIf(days_without_touch<=3,'1. до 3 дней',days_without_touch<=7,'2. 4-7 дней',
   days_without_touch<=14,'3. 8-14 дней','4. больше 14 дней') AS korzina, count() AS sdelok
   FROM data_marts.dm__sales_funnel_cycles
   WHERE is_cycle_completed=0 AND is_paid_cycle=0 AND days_without_touch IS NOT NULL
   GROUP BY korzina ORDER BY korzina FORMAT TSVWithNames""",
}

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    if a[0] == "таблицы":
        print(q("SELECT name, formatReadableQuantity(total_rows) AS strok FROM system.tables "
                "WHERE database='data_marts' ORDER BY name FORMAT TSVWithNames")); return
    if a[0] == "колонки" and len(a) > 1:
        print(q(f"SELECT name, type FROM system.columns WHERE database='data_marts' "
                f"AND table='{a[1]}' FORMAT TSVWithNames")); return
    if a[0] in PRESETS:
        n = int(a[1]) if len(a) > 1 and a[1].isdigit() else 8
        print(q(PRESETS[a[0]](n))); return
    sql = " ".join(a)
    if "format" not in sql.lower(): sql += " FORMAT TSVWithNames"
    print(q(guard(sql)))

if __name__ == "__main__":
    main()
