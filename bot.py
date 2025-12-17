import requests
import json
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

USD_ID = 431
EUR_ID = 451
DATA_FILE = 'rates.json'


def is_workday(date):
    return date.weekday() < 5  # 0–4 = Пн–Пт


def get_rate(cur_id):
    url = f'https://www.nbrb.by/api/exrates/rates/{cur_id}'
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_message(text):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    requests.post(url, json={
        'chat_id': CHAT_ID,
        'text': text
    })


def send_photo(path, caption):
    url = f'https://api.telegram.org/bot{TOKEN}/sendPhoto'
    with open(path, 'rb') as f:
        requests.post(url, data={
            'chat_id': CHAT_ID,
            'caption': caption
        }, files={'photo': f})


def build_chart(history, code):
    dates = list(history.keys())[-30:]
    values = [history[d] for d in dates]

    plt.figure(figsize=(8, 4))
    plt.plot(dates, values, marker='o')
    plt.title(f'{code} — НБРБ (30 дней)')
    plt.xticks(rotation=45)
    plt.tight_layout()

    filename = f'{code}.png'
    plt.savefig(filename)
    plt.close()

    return filename


def main():
    today = datetime.now()

    if not is_workday(today):
        return

    data = load_data()

    message = ['💱 Курс НБРБ:']
    charts = []

    for cur_id in (USD_ID, EUR_ID):
        cur = get_rate(cur_id)

        code = cur['Cur_Abbreviation']
        rate = cur['Cur_OfficialRate']
        date = cur['Date'][:10]

        history = data.setdefault(code, {})

        yesterday = (datetime.fromisoformat(date) - timedelta(days=1)).date().isoformat()
        diff = None
        if yesterday in history:
            diff = rate - history[yesterday]

        history[date] = rate

        if diff is None:
            message.append(f'{code}: {rate}')
        else:
            sign = '🔺' if diff > 0 else '🔻'
            message.append(f'{code}: {rate} ({sign}{diff:.4f})')

        charts.append(build_chart(history, code))

    save_data(data)
    send_message('\n'.join(message))

    for chart in charts:
        send_photo(chart, '📊 Динамика за месяц')


if __name__ == '__main__':
    main()
