import requests
import json
import os
from datetime import datetime, timedelta, date
import matplotlib.pyplot as plt

# ================== CONFIG ==================

TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

DATA_FILE = 'rates.json'
META_FILE = 'meta.json'

CURRENCIES = ('USD', 'EUR')

API_URLS = [
    'https://www.nbrb.by/api/exrates/rates',
    'https://api.nbrb.by/exrates/rates',
]

# ================== UTILS ==================

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ================== TELEGRAM ==================

def send_message(text):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    requests.post(url, json={
        'chat_id': CHAT_ID,
        'text': text
    })


def send_photo(path, caption):
    url = f'https://api.telegram.org/bot{TOKEN}/sendPhoto'
    with open(path, 'rb') as f:
        requests.post(
            url,
            data={'chat_id': CHAT_ID, 'caption': caption},
            files={'photo': f}
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
            print(f'API failed {base_url} ({target_date}): {e}')

    return None

# ================== CHART ==================

def build_chart(history, code):
    dates = sorted(history.keys())[-30:]
    values = [history[d] for d in dates]

    plt.figure(figsize=(8, 4))
    plt.plot(dates, values, marker='o')
    plt.title(f'{code} — НБРБ (30 дней)')
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()

    filename = f'{code}.png'
    plt.savefig(filename)
    plt.close()

    return filename

# ================== MAIN ==================

def main():
    rates_data = load_json(DATA_FILE, {})
    meta = load_json(META_FILE, {})

    last_known_date = meta.get('last_date')

    if last_known_date:
        target_date = (
            datetime.fromisoformat(last_known_date).date()
            + timedelta(days=1)
        )
    else:
        target_date = date.today()

    rates = request_rates(target_date)

    if not rates:
        print(f'No data for {target_date}, waiting')
        return

    rate_date = next(iter(rates.values()))['Date'][:10]

    # ❗️Если дата не новее — ничего не делаем
    if last_known_date and rate_date <= last_known_date:
        print(f'Date {rate_date} already processed')
        return

    message = [f'💱 Курс НБРБ на {rate_date}:']
    charts = []

    for code in CURRENCIES:
        cur = rates[code]
        rate = cur['Cur_OfficialRate']

        history = rates_data.setdefault(code, {})

        prev_date = (
            datetime.fromisoformat(rate_date) - timedelta(days=1)
        ).date().isoformat()

        diff = None
        if prev_date in history:
            diff = rate - history[prev_date]

        history[rate_date] = rate

        if diff is None:
            message.append(f'{code}: {rate}')
        else:
            sign = '🔺' if diff > 0 else '🔻'
            message.append(f'{code}: {rate} ({sign}{diff:.4f})')

        charts.append(build_chart(history, code))

    rates_data = rates_data
    meta['last_date'] = rate_date

    save_json(DATA_FILE, rates_data)
    save_json(META_FILE, meta)

    send_message('\n'.join(message))

    for chart in charts:
        send_photo(chart, '📊 Динамика за месяц')

# ================== RUN ==================

if __name__ == '__main__':
    main()
