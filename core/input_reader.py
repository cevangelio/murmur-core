import os
import json
from datetime import datetime

def read_logs(log_dir):
    entries = []
    for filename in sorted(os.listdir(log_dir)):
        if filename.endswith(".log"):
            with open(os.path.join(log_dir, filename), 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        formatted = format_log_entry(entry)
                        entries.append(formatted)
                    except json.JSONDecodeError:
                        continue
    return "\n".join(entries)

def format_log_entry(entry):
    ts = entry.get("timestamp", "")
    if entry.get("type") == "news_event":
        return f"[News Event @ {ts}] {entry['title']} ({entry['currency']}, {entry['impact']}) - Forecast: {entry['forecast']}, Actual: {entry['actual']}"
    elif entry.get("type") == "snapshot":
        return f"[Snapshot @ {ts}] {entry['pair']} - Units: {entry['units']}, Price: {entry['live_price']}, PnL: {entry['pips']} pips"
    else:
        return f"[Unknown Entry @ {ts}] {entry}"