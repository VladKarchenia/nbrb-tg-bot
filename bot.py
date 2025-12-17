import requests
import json
import os
from datetime import datetime, timedelta, date
import matplotlib.pyplot as plt

# ================== CONFIG ==================

TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

DATA_FILE = 'rates.json'

CURRENCIES = ('USD', 'EUR')

# Официальные нерабочие дни РБ (можно дополнять)
HOLIDAYS = {
    '2025-01-01',  # Новый год
    '2025-01-07',  # Рождество
    '2025-03-08',  # 8 марта
    '2025-05-01',  # Праздник труда
    '2025-05-09',  # День Победы
    '2025-07-03',  # День Независимости
    '2025-11-07',  # День Октябрьской революции
    '2025-12-25',  # Рождество (католическое)
}

# ================== HELPERS ==================

def is_workday(dt: datetime) -> bool:
    if dt.weekday() >= 5:  # суббота, воскресенье
        return False
    if dt.date().isoformat() in HOLIDAYS:
        return False
    return True


def get_rates():
    """
    Получаем курсы одним запросом + fallback
    """
    urls = [
        'https://www.nbrb.by/api/exrates/rates?periodicity=0',
        'https://api.nbrb.by/exrates/rates?periodicity=0',
    ]

    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()

            result = {}
            for cur in data:
                if cur['Cur_Abbreviation'] in CURRENCIES:
                    result[cur['Cur_Abbreviation']] = cur

            if len(result) == len(CURRENCIES):
                return result

        except Exception as e:
            print(f'API failed: {url} → {e}')

    raise RuntimeError('NBRB API unreachable')


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


def build_chart(history: dict, code: str) -> str:
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
    today = datetime.now()

    # ⏰ только рабочие дни
    if not is_workday(today):
        print('Not a workday, skipping')
        return

    try:
        rates = get_rates()
    except Exception as e:
        send_message(f'⚠️ Не удалось получить курс НБРБ:\n{e}')
        return

    data = load_data()
    message = ['💱 Курс НБРБ:']
    charts = []

    for code in CURRENCIES:
        cur = rates[code]

        rate = cur['Cur_OfficialRate']
        rate_date = cur['Date'][:10]

        history = data.setdefault(code, {})

        yesterday = (
            datetime.fromisoformat(rate_date) - timedelta(days=1)
        ).date().isoformat()

        diff = None
        if yesterday in history:
            diff = rate - history[yesterday]

        history[rate_date] = rate

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
