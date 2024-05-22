import os

# 設置 MPLCONFIGDIR 環境變量到 /tmp 目錄
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

import datetime
import matplotlib.pyplot as plt
from flask import Flask, render_template, url_for, send_from_directory
import threading
import time
import matplotlib.dates as mdates

app = Flask(__name__)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

def read_yesterday_file(suffix):
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    filename = yesterday.strftime(f'%Y-%m-%d-{suffix}.txt')
    filepath = os.path.join('data', filename)
    if not os.path.exists(filepath):
        print(f"File {filepath} does not exist. Skipping.")
        return []
    with open(filepath, 'r') as file:
        lines = file.readlines()
    return lines

def parse_data(lines):
    data = {
        "timestamp": [],
        "PM2.5": [],
        "PM10": [],
        "temperature": [],
        "humidity": [],
        "TVOC": [],
        "CO": []
    }

    previous_time = None
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 3:
            print(f"Skipping malformed line: {line}")
            continue
        time_str = parts[1]
        values = parts[2].split(',')
        if len(values) < 16:
            print(f"Skipping malformed data: {values}")
            continue
        try:
            time_obj = datetime.datetime.strptime(time_str, "%H:%M:%S")
            if previous_time and (time_obj - previous_time).total_seconds() > 300:
                # 如果時間差超過5分鐘，插入空值
                data["timestamp"].append(previous_time + datetime.timedelta(seconds=1))
                data["PM2.5"].append(None)
                data["PM10"].append(None)
                data["temperature"].append(None)
                data["humidity"].append(None)
                data["TVOC"].append(None)
                data["CO"].append(None)
            data["timestamp"].append(time_obj)
            data["PM2.5"].append(float(values[11]))
            data["PM10"].append(float(values[12]))
            data["temperature"].append(float(values[13]))
            data["humidity"].append(float(values[14]))
            data["TVOC"].append(float(values[15]))
            data["CO"].append(float(values[16]))
            previous_time = time_obj
        except (IndexError, ValueError) as e:
            print(f"Error parsing line: {line}, error: {e}")
            continue

    return data

def calculate_upper_limit(value, step):
    """計算上限，使其尾數為0或5"""
    return (int(value / step) + 1) * step

def plot_data(data, suffix):
    # 設置字體大小
    plt.rcParams.update({'font.size': 16})  # 調整此數值以設置所需的字體大小
    
    # 確保數據不為空
    if not data["timestamp"]:
        raise ValueError("No valid data found to plot.")
    
    fig, axs = plt.subplots(3, 1, figsize=(15, 20))

    # 設定時間標籤和格式
    time_labels = [datetime.datetime.strptime(f"{hour:02d}:00:00", "%H:%M:%S") for hour in range(0, 24, 2)]
    time_labels.append(datetime.datetime.strptime("23:59:59", "%H:%M:%S"))
    
    # 過濾掉 None 值
    co_values = [v for v in data["CO"] if v is not None]
    tvoc_values = [v for v in data["TVOC"] if v is not None]
    pm25_values = [v for v in data["PM2.5"] if v is not None]
    pm10_values = [v for v in data["PM10"] if v is not None]

    # CO 和 TVOC
    max_co = max(co_values, default=2.0)
    max_tvoc = max(tvoc_values, default=2.0)
    max_val = max(max_co, max_tvoc, 2.0)
    upper_limit = calculate_upper_limit(max_val, 0.5)  # 動態設置上限，並取0.5的倍數
    interval = upper_limit / 10  # 動態設置間隔

    axs[0].plot(data["timestamp"], data["CO"], label='CO', color='orange')
    axs[0].plot(data["timestamp"], data["TVOC"], label='TVOC', color='blue')
    axs[0].set_title(f'CO & TVOC ({suffix})')
    axs[0].xaxis.set_major_locator(mdates.HourLocator(interval=2))
    axs[0].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    axs[0].set_xlim(time_labels[0], time_labels[-1])
    axs[0].set_ylim(0, upper_limit)
    axs[0].set_yticks([i * interval for i in range(int(upper_limit / interval) + 1)])
    axs[0].legend()

    # 溫度和濕度
    ax2 = axs[1].twinx()  # 創建第二個Y軸
    axs[1].plot(data["timestamp"], data["temperature"], label='Temperature', color='tab:red')
    ax2.plot(data["timestamp"], data["humidity"], label='Humidity', color='tab:blue')
    axs[1].set_title(f'Temperature & Humidity ({suffix})')
    axs[1].set_xlabel('Time')
    axs[1].set_ylabel('Temperature (°C)', color='tab:red')
    axs[1].xaxis.set_major_locator(mdates.HourLocator(interval=2))
    axs[1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    axs[1].set_xlim(time_labels[0], time_labels[-1])
    axs[1].set_ylim(0, 40)
    axs[1].set_yticks([i * 5 for i in range(9)])
    for tl in axs[1].get_yticklabels():
        tl.set_color('tab:red')

    ax2.set_ylabel('Humidity (%)', color='tab:blue')
    ax2.set_ylim(0, 100)
    ax2.set_yticks([i * 10 for i in range(11)])
    for tl in ax2.get_yticklabels():
        tl.set_color('tab:blue')

    axs[1].legend(loc='upper left')
    ax2.legend(loc='upper right')

    # PM2.5 和 PM10
    max_pm25 = max(pm25_values, default=100)
    max_pm10 = max(pm10_values, default=100)
    max_pm_val = max(max_pm25, max_pm10, 100)
    upper_limit_pm = calculate_upper_limit(max_pm_val, 5)  # 動態設置上限，並取5的倍數
    interval_pm = 10 if upper_limit_pm <= 100 else calculate_upper_limit(upper_limit_pm / 10, 5)  # 動態設置間隔

    axs[2].plot(data["timestamp"], data["PM2.5"], label='PM2.5')
    axs[2].plot(data["timestamp"], data["PM10"], label='PM10')
    axs[2].set_title(f'PM2.5 & PM10 ({suffix})')
    axs[2].xaxis.set_major_locator(mdates.HourLocator(interval=2))
    axs[2].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    axs[2].set_xlim(time_labels[0], time_labels[-1])
    axs[2].set_ylim(0, upper_limit_pm)
    axs[2].set_yticks([i * interval_pm for i in range(int(upper_limit_pm / interval_pm) + 1)])
    axs[2].legend()

    plt.tight_layout()
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    plot_file_name = yesterday.strftime(f'%Y-%m-%d-{suffix}.png')
    plot_file_path = os.path.join('data', plot_file_name)
    plt.savefig(plot_file_path)
    plt.close(fig)
    print(f"Plot saved as {plot_file_path}")
    return plot_file_name

def update_data():
    while True:
        time.sleep(60)  # 這裡的時間間隔可以根據實際需求進行調整
        for suffix in ["office", "factory"]:
            lines = read_yesterday_file(suffix)
            data = parse_data(lines)
            if data["timestamp"]:
                plot_data(data, suffix)

@app.route('/')
def index():
    return "Data plotting service is running."

if __name__ == '__main__':
    threading.Thread(target=update_data).start()
    app.run(debug=True)
