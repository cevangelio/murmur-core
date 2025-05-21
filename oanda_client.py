import requests
import json
import logging
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()
HOME = str(Path.home())

logging.basicConfig(
    filename=f"{HOME}/Documents/MacTrader/SkyeFX/SkyEngine/logs/SkyeEngine_NFPxTI.log", 
    encoding='utf-8', 
    level=logging.DEBUG,
    format='%(asctime)s:    %(levelname)s:  %(module)s  %(message)s'
)

class OandaClient:
    BASE_URL = os.getenv("OANDA_BASE_URL")  # Use api-fxtrade.oanda.com for live accounts OR api-fxpractice.oanda.com

    def __init__(self, api_key):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def get_candles(self, pair, count=200, granularity="D", price='M'):
        url = f"{self.BASE_URL}/instruments/{pair}/candles"
        params = {
            "count": count,
            "price": price,
            "granularity": granularity
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_price_now(self, pair):
        url = f"{self.BASE_URL}/pricing"
        params = {"instruments": pair}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def place_market_order(self, account_id, instrument, units):
        """
        Places a market order on OANDA.
        
        :param account_id: OANDA account ID
        :param instrument: Trading pair (e.g., "EUR_USD")
        :param units: Number of units to buy/sell (negative for selling)
        :return: Response JSON from the API
        """
        url = f"{self.BASE_URL}/accounts/{account_id}/orders"
        
        payload = {
                "order": {
                "units": str(units),
                "instrument": instrument,
                "timeInForce": "FOK",
                "type": "MARKET",
                "positionFill": "DEFAULT"
            }
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()  # Raise an error for bad responses
        return response.json()


    def get_open_trades(self, account_id):
        """
        Fetch all currently open trades from Oanda API.
        Returns a list of trade dictionaries.
        """
        url = f"{self.BASE_URL}/accounts/{account_id}/openTrades"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json().get("trades", [])
        else:
            logging.error(f"Error fetching open trades: {response.status_code} - {response.text}")
            return []

    def close_trade(self, account_id, trade_id):
        """
        Closes a trade by its trade ID.
        """
        url = f"{self.BASE_URL}/accounts/{account_id}/trades/{trade_id}/close"
        response = requests.put(url, headers=self.headers)
        if response.status_code == 200:
            logging.info(f"Successfully closed trade {trade_id}")
            return response.json()
        else:
            logging.error(f"Error closing trade {trade_id}: {response.status_code} - {response.text}")
            return None
        
    def get_pnl(self, account_id):
        url = f"{self.BASE_URL}/accounts/{account_id}/summary"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            logging.info(f"Successfully retrieved account summary.")
            raw = response.json()
            return raw['account']['unrealizedPL']
        else:
            logging.error(f"Error retrieving account summary.: {response.status_code} - {response.text}")
            return None
        
    def get_account_balance(self, account_id):
        """
        Fetches the account balance from Oanda API.
        """
        url = f"{self.BASE_URL}/accounts/{account_id}"
        response = requests.get(url, headers=self.headers)
        print(response.text)
        account_balance = response.json()['account']['balance']
        return account_balance

    def get_total_pips(self, account_id):
    # Similar to what your dashboard does
        url = f"{self.BASE_URL}/accounts/{account_id}/openTrades"
        response = requests.get(url, headers=self.headers)
        total_pips = 0

        if response.status_code == 200:
            trades = response.json().get("trades", [])
            instruments = [t["instrument"] for t in trades]
            prices = {}

            if instruments:
                price_url = f"{self.BASE_URL}/accounts/{account_id}/pricing?instruments={','.join(instruments)}"
                price_resp = requests.get(price_url, headers=self.headers)
                if price_resp.status_code == 200:
                    prices = {p["instrument"]: float(p["closeoutAsk"]) for p in price_resp.json().get("prices", [])}

            for trade in trades:
                instrument = trade["instrument"]
                units = int(trade["currentUnits"])
                open_price = float(trade["price"])
                live_price = prices.get(instrument, open_price)
                pip_value = 0.0001 if "JPY" not in instrument else 0.01
                pips = (live_price - open_price) / pip_value
                pips = pips if units > 0 else -pips
                total_pips += pips

        return total_pips
    
    def fetch_closed_trades_summary(self, account_id, start_date, end_date):
        """
        Fetch closed trades summary (total trades, realized profit in SGD, and properly calculated pips).
        Corrects pip sizing for JPY pairs based on open price.
        """
        url = f"{self.BASE_URL}/accounts/{account_id}/trades"
        params = {
            "state": "CLOSED"
        }

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        data = response.json()

        total_trades = 0
        total_realized_pl = 0.0
        total_pips = 0.0

        print("\n🛠 Debugging closed trades fetched:")

        for trade in data.get("trades", []):
            close_time = trade.get("closeTime")
            if close_time:
                close_date = close_time[:10]
                if start_date <= close_date <= end_date:
                    instrument = trade.get("instrument")
                    realized_pl = float(trade.get("realizedPL", 0.0))
                    units = int(trade.get("initialUnits", 0))
                    open_price = float(trade.get("price", 0.0))

                    if units == 0 or open_price == 0.0:
                        continue  # Skip invalid entries

                    # Determine pip size
                    pip_size = 0.01 if "JPY" in instrument else 0.0001

                    # Pip value per unit (correct for JPY pairs)
                    if "JPY" in instrument:
                        pip_value_per_unit = pip_size / open_price
                    else:
                        pip_value_per_unit = pip_size

                    # Calculate pips
                    pips = abs(realized_pl) / (abs(units) * pip_value_per_unit)

                    # Keep sign same as realizedPL
                    if realized_pl < 0:
                        pips = -pips

                    print(f"🔹 {instrument} | Units: {units} | Open: {open_price:.5f} | RealizedPL: {realized_pl:.4f} | Pips: {pips:.1f}")

                    total_realized_pl += realized_pl
                    total_pips += pips
                    total_trades += 1

        print(f"\n✅ Total Trades: {total_trades}")
        print(f"✅ Total Realized Profit (SGD): {round(total_realized_pl, 2)}")
        print(f"✅ Total True Pips: {round(total_pips, 1)}\n")

        return {
            "total_trades": total_trades,
            "final_profit": round(total_realized_pl, 2),
            "final_pips": round(total_pips, 1)
        }
