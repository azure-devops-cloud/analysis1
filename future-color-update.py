import os
import time
import logging
import pandas as pd
from datetime import datetime
from binance.client import Client
import requests
from colorama import Fore, Style

# Binance API setup
API_KEY = "xxx"
API_SECRET = "xxxxx"
client = Client(API_KEY, API_SECRET)

# CSV file for saving data
CSV_FILE = "order_book_predictions.csv"
INTERVAL = 10  # Fetch data every 10 seconds

# Telegram Notification Setup
TELEGRAM_BOT_TOKEN = "7634717158:AAHMMksZXje9CEF4qEMn3Vgge5F_qNs6sHg"
TELEGRAM_CHAT_ID = "5463783915"
TELEGRAM_GROUP_ID = "-4695344604"

# Logging setup
logging.basicConfig(
    filename="order_book_predictions.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Track last alerted whale volume to prevent duplicate alerts
last_alerted_buy_volume = 0
last_alerted_sell_volume = 0

# Fetch latest BTC/USDT price
def get_btc_price():
    try:
        ticker = client.futures_symbol_ticker(symbol="BTCUSDT")
        return float(ticker["price"])
    except Exception as e:
        logging.error(f"Error fetching BTC price: {e}")
        return None

# Initialize CSV file
def initialize_csv(file_name):
    if not os.path.exists(file_name):
        df = pd.DataFrame(columns=[
            "timestamp", "btc_price", "total_bid_volume", "total_ask_volume",
            "largest_buy_wall_price", "largest_buy_wall_volume",
            "largest_sell_wall_price", "largest_sell_wall_volume",
            "spread", "prediction", "whale_alert"
        ])
        df.to_csv(file_name, index=False)

# Fetch order book data
def fetch_order_book(symbol="BTCUSDT", limit=100):
    try:
        return client.futures_order_book(symbol=symbol, limit=limit)
    except Exception as e:
        logging.error(f"Error fetching order book: {e}")
        return None

# Send Telegram Notification
def send_telegram_notification(message, alert_type="info"):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        emoji = "🟢" if "Buy Order" in message else "🔴"  # Assign color indicator

        formatted_message = f"🚨 *{emoji} Whale Alert!*\n\n{message}"

        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": formatted_message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            logging.info(f"Telegram Alert Sent: {message}")
        else:
            logging.error(f"Failed to send Telegram message: {response.text}")

    except Exception as e:
        logging.error(f"Error sending Telegram message: {e}")

# Analyze order book
def analyze_order_book(order_book):
    global last_alerted_buy_volume, last_alerted_sell_volume
    try:
        bids = order_book["bids"]
        asks = order_book["asks"]
        
        total_bid_volume = sum([float(b[1]) for b in bids])
        total_ask_volume = sum([float(a[1]) for a in asks])
        largest_buy_wall = max(bids, key=lambda b: float(b[1]))
        largest_sell_wall = max(asks, key=lambda a: float(a[1]))
        spread = float(asks[0][0]) - float(bids[0][0])

        whale_alert = ""

        # Large Buy Order Alert
        buy_volume = float(largest_buy_wall[1])
        if buy_volume >= 10 and buy_volume // 10 > last_alerted_buy_volume // 10:
            whale_alert = (
                #f"🐳 *Large Buy Order Detected!*\n"
                f"💰 *Volume:* `{buy_volume} BTC`\n"
                f"📍 *Price:* `{largest_buy_wall[0]}`\n"
                f"📈 *Market Price:* `{asks[0][0]}`\n🟢"
            )
            send_telegram_notification(whale_alert, "buy")
            last_alerted_buy_volume = buy_volume
            print(Fore.GREEN + f"🚨 {whale_alert}" + Style.RESET_ALL)  # Green for Buy

        # Large Sell Order Alert
        sell_volume = float(largest_sell_wall[1])
        if sell_volume >= 10 and sell_volume // 10 > last_alerted_sell_volume // 10:
            whale_alert = (
                #f"🐳 *Large Sell Order Detected!*\n"
                f"💰 *Volume:* `{sell_volume} BTC`\n"
                f"📍 *Price:* `{largest_sell_wall[0]}`\n"
                f"📉 *Market Price:* `{bids[0][0]}`\n🔴"
            )
            send_telegram_notification(whale_alert, "sell")
            last_alerted_sell_volume = sell_volume
            print(Fore.RED + f"🚨 {whale_alert}" + Style.RESET_ALL)  # Red for Sell

        return {
            "total_bid_volume": total_bid_volume,
            "total_ask_volume": total_ask_volume,
            "largest_buy_wall": (float(largest_buy_wall[0]), buy_volume),
            "largest_sell_wall": (float(largest_sell_wall[0]), sell_volume),
            "spread": spread,
            "whale_alert": whale_alert
        }
    except Exception as e:
        logging.error(f"Error analyzing order book: {e}")
        return None

# Predict market sentiment
def predict_sentiment(analysis):
    if analysis["total_bid_volume"] > analysis["total_ask_volume"]:
        return "Bullish 🟢"
    elif analysis["total_bid_volume"] < analysis["total_ask_volume"]:
        return "Bearish 🔴"
    else:
        return "Neutral ⚪"

# Save data to CSV
def save_to_csv(data, file_name=CSV_FILE):
    try:
        df = pd.DataFrame([data])
        with open(file_name, mode="a", newline="") as f:
            df.to_csv(f, index=False, header=False)
            f.flush()  # Ensure data is written immediately
    except Exception as e:
        logging.error(f"Error saving to CSV: {e}")

# Main loop
def main():
    initialize_csv(CSV_FILE)
    while True:
        start_time = time.time()  # Record start time

        try:
            order_book = fetch_order_book()
            btc_price = get_btc_price()

            if order_book and btc_price:
                analysis = analyze_order_book(order_book)
                if analysis:
                    prediction = predict_sentiment(analysis)

                    # Define timestamp before printing
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    data = {
                        "timestamp": timestamp,
                        "btc_price": btc_price,
                        "total_bid_volume": analysis["total_bid_volume"],
                        "total_ask_volume": analysis["total_ask_volume"],
                        "largest_buy_wall_price": analysis["largest_buy_wall"][0],
                        "largest_buy_wall_volume": analysis["largest_buy_wall"][1],
                        "largest_sell_wall_price": analysis["largest_sell_wall"][0],
                        "largest_sell_wall_volume": analysis["largest_sell_wall"][1],
                        "spread": analysis["spread"],
                        "prediction": prediction,
                        "whale_alert": analysis["whale_alert"]
                    }

                    # Save data to CSV
                    save_to_csv(data)

                    # Print in command prompt with BTC price
                    color = Fore.GREEN if "Bullish" in prediction else Fore.RED
                    print(color + f"[{timestamp}] Price: {btc_price:.2f} USDT | "
                                  f"Buy: {analysis['largest_buy_wall'][1]} BTC | "
                                  f"Sell: {analysis['largest_sell_wall'][1]} BTC | Prediction: {prediction}"
                          + Style.RESET_ALL, flush=True)

                    # Print Whale Alert if detected
                    if analysis["whale_alert"]:
                        print(Fore.YELLOW + f"🚨 {analysis['whale_alert']} (BTC Price: {btc_price:.2f})" + Style.RESET_ALL)

                logging.info(f"Data saved: {data}")

        except Exception as e:
            logging.error(f"Error in main loop: {e}")

        # Ensure 10-second interval execution
        elapsed_time = time.time() - start_time
        time.sleep(max(0, INTERVAL - elapsed_time))

if __name__ == "__main__":
    main()
