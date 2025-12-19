import requests
import json
import os
from datetime import datetime, timedelta, date
import time
import matplotlib.pyplot as plt

# ================== CONFIG ==================

BOT_TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

DATA_FILE = 'rates.json'

CURRENCIES = ('USD', 'EUR')

API_URLS = [
    'https://www.nbrb.by/api/exrates/rates',
    'https://api.nbrb.by/exrates/rates',
]

CHART_DAYS = 30

# ================== STORAGE ==================

def load_rates():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_rates(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ================== TELEGRAM ==================

def send_message(text):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    requests.post(
        url,
        json={'chat_id': CHAT_ID, 'text': text},
        timeout=10
    )


def send_photo(path, caption):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto'
    with open(path, 'rb') as f:
        requests.post(
            url,
            data={'chat_id': CHAT_ID, 'caption': caption},
            files={'photo': f},
            timeout=20
        )

# ================== NBRB ==================

def request_rates(target_date: date):
    for base_url in API_URLS:
        try:
            r = requests.get(
                base_url,
                params={
                    'ondate': target_date.isoformat(),
                    'periodicity': 0
                },
                timeout=15
            )
            r.raise_for_status()
            data = r.json()

            if not data:
                continue

            result = {
                cur['Cur_Abbreviation']: cur
                for cur in data
                if cur['Cur_Abbreviation'] in CURRENCIES
            }

            if len(result) == len(CURRENCIES):
                return result

        except Exception as e:
            print(f'API error {base_url} {target_date}: {e}')

    return None

# ================== CHART ==================

def build_chart(history: dict, code: str):
    dates = sorted(history.keys())[-CHART_DAYS:]
    values = [history[d] for d in dates]

    plt.figure(figsize=(8, 4))
    plt.plot(dates, values, marker='o')
    plt.title(f'{code} — НБРБ (последние {len(dates)} дней)')
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()

    filename = f'{code}_chart.png'
    plt.savefig(filename)
    plt.close()

    return filename

# ================== CORE LOGIC ==================

def get_start_date(rates_data):
    all_dates = set()
    for cur in rates_data.values():
        all_dates.update(cur.keys())

    if not all_dates:
        return date.today()

    last_date = max(datetime.fromisoformat(d).date() for d in all_dates)
    return last_date + timedelta(days=1)


def process_rates():
    rates_data = load_rates()
    current_date = get_start_date(rates_data)

    print(f'Start checking from {current_date}')

    while True:
        rates = request_rates(current_date)

        # если данных нет — выходим и ждём следующего цикла
        if not rates:
            print(f'No data for {current_date}, stop')
            break

        date_str = current_date.isoformat()

        # проверяем, сохранена ли дата
        already_saved = True
        for code in CURRENCIES:
            if date_str not in rates_data.get(code, {}):
                already_saved = False
                break

        # если дата новая — сохраняем, шлём сообщение и графики
        if not already_saved:
            message = [f'💱 Курс НБРБ на {date_str}:']

            for code in CURRENCIES:
                rate = rates[code]['Cur_OfficialRate']
                rates_data.setdefault(code, {})[date_str] = rate
                message.append(f'{code}: {rate}')

            save_rates(rates_data)
            send_message('\n'.join(message))
            print(f'Sent new rates for {date_str}')

            # строим и отправляем графики
            for code in CURRENCIES:
                chart = build_chart(rates_data[code], code)
                send_photo(chart, f'📊 {code}: последние {CHART_DAYS} дней')

        else:
            print(f'Date {date_str} already saved')

        # идём дальше
        current_date += timedelta(days=1)

# ================== LOOP ==================

def main():
    process_rates()

# ================== RUN ==================

if __name__ == '__main__':
    main()
