import requests
import json
import os
from datetime import datetime, timedelta, date
import matplotlib.pyplot as plt

# ================== CONFIG ==================

TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

DATA_FILE = 'rates.json'
META_FILE = 'meta.json'  # хранит последнюю отправленную дату

CURRENCIES = ('USD', 'EUR')

# ================== STORAGE ==================

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


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

# ================== NBRB API ==================

def get_rates_with_tomorrow_fallback():
    """
    Пытаемся получить курс на завтра.
    Если его ещё нет — берём курс на сегодня.
    Возвращаем (rates, rate_date)
    """

    today = date.today()
    tomorrow = today + timedelta(days=1)

    urls = [
        'https://www.nbrb.by/api/exrates/rates',
        'https://api.nbrb.by/exrates/rates',
    ]

    for target_date in (tomorrow, today):
        for base_url in urls:
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

                result = {}
                for cur in data:
                    if cur['Cur_Abbreviation'] in CURRENCIES:
                        result[cur['Cur_Abbreviation']] = cur

                if len(result) == len(CURRENCIES):
                    return result, target_date

            except Exception as e:
                print(f'API failed {base_url} ({target_date}): {e}')

    raise RuntimeError('NBRB API unreachable')

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

    try:
        rates, api_date = get_rates_with_tomorrow_fallback()
    except Exception as e:
        send_message(f'⚠️ Не удалось получить курс НБРБ:\n{e}')
        return

    rate_date = next(iter(rates.values()))['Date'][:10]

    # ❗ Уже отправляли эту дату — выходим
    if meta.get('last_sent_date') == rate_date:
        print(f'Already sent for {rate_date}')
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

    # сохраняем историю и мету
    save_json(DATA_FILE, rates_data)
    save_json(META_FILE, {'last_sent_date': rate_date})

    send_message('\n'.join(message))

    for chart in charts:
        send_photo(chart, '📊 Динамика за месяц')

# ================== RUN ==================

if __name__ == '__main__':
    main()
