import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import requests
from dotenv import load_dotenv
from oanda_client import OandaClient

# === CONFIG ===
LOGS_DIR_FOLDER_ID = datetime.strftime(datetime.now(), "%Y/%B%Y")
LOGS_DIR = f"/Volumes/MacHDD/Downloads/SkyeFX/blog_logs/{LOGS_DIR_FOLDER_ID}"
OUTPUT_DIR = f"{LOGS_DIR}/generated_posts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

STRATEGY_NAME = "BlueFire"
AUTHOR = "Amber"
YEAR_MONTH_ID = datetime.strftime(datetime.now(), "%Y-%m")
load_dotenv()

OANDA_API_KEY = os.getenv("OANDA_API_KEY")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
OANDA_BASE_URL = os.getenv("OANDA_BASE_URL")
OANDA_CLIENT = OandaClient(OANDA_API_KEY)


# === FUNCTIONS ===

def load_all_logs(logs_dir):
    entries = []
    for filename in sorted(os.listdir(logs_dir)):
        if filename.startswith(f"blog_logs_{YEAR_MONTH_ID}") and filename.endswith(".log"):
            file_path = os.path.join(logs_dir, filename)
            with open(file_path, "r") as f:
                for line in f:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue  # Skip broken lines
    return entries


def extract_filtered_logs(logs):
    snapshots = [log for log in logs if log["type"] == "snapshot"]
    news_events = []
    seen_news = set()
    for log in logs:
        if log["type"] == "news_event":
            identifier = (log["title"], log["timestamp"])
            if identifier not in seen_news:
                news_events.append(log)
                seen_news.add(identifier)

    def get_minute_bucket(ts):
        dt = datetime.fromisoformat(ts)
        return dt.replace(second=0, microsecond=0).isoformat()

    basket_groups = defaultdict(list)
    for snap in snapshots:
        minute_key = get_minute_bucket(snap["timestamp"])
        basket_groups[minute_key].append(snap)

    basket_scores = {}
    for ts, snaps in basket_groups.items():
        total_pips = sum(s["pips"] for s in snaps if "pips" in s)
        basket_scores[ts] = total_pips

    highest_basket_pips = float('-inf')
    lowest_basket_pips = float('inf')
    highest_basket_ts = []
    lowest_basket_ts = []

    for ts, total_pips in basket_scores.items():
        if total_pips > highest_basket_pips:
            highest_basket_pips = total_pips
            highest_basket_ts = [ts]
        elif total_pips == highest_basket_pips:
            highest_basket_ts.append(ts)

        if total_pips < lowest_basket_pips:
            lowest_basket_pips = total_pips
            lowest_basket_ts = [ts]
        elif total_pips == lowest_basket_pips:
            lowest_basket_ts.append(ts)

    summary_entries = []
    if highest_basket_ts:
        summary_entries.append({
            "type": "basket_summary",
            "label": "Highest Basket",
            "timestamp": highest_basket_ts[0],
            "basket_total_pips": round(highest_basket_pips, 1)
        })
    if lowest_basket_ts:
        summary_entries.append({
            "type": "basket_summary",
            "label": "Lowest Basket",
            "timestamp": lowest_basket_ts[0],
            "basket_total_pips": round(lowest_basket_pips, 1)
        })

    all_snapshots = snapshots
    first_snapshot = snapshots[0] if snapshots else {}
    last_snapshot = snapshots[-1] if snapshots else {}

    return {
        "snapshots": all_snapshots,
        "news_events": news_events,
        "summary_entries": summary_entries,
        "first_snapshot": first_snapshot,
        "last_snapshot": last_snapshot,
        "basket_scores": basket_scores
    }


def extract_summary(filtered_data):
    snapshots = filtered_data["snapshots"]
    summary_entries = filtered_data["summary_entries"]
    news_events = filtered_data["news_events"]
    basket_scores = filtered_data["basket_scores"]

    if not snapshots:
        raise ValueError("Not enough data to build a summary.")

    basket_start_date = snapshots[0]["timestamp"][:10]
    basket_end_date = snapshots[-1]["timestamp"][:10]

    timestamps_sorted = sorted(basket_scores.keys())
    basket_pips_list = []

    print("\n🛠 Basket Scores (Per Minute):")
    for ts in timestamps_sorted:
        basket_pips = basket_scores[ts]
        basket_pips_list.append([ts, basket_pips])
        print(f"{ts} | Basket Pips: {round(basket_pips, 1)}")

    basket_df = pd.DataFrame(basket_pips_list, columns=["timestamp", "basket_pips"])
    basket_df["timestamp"] = pd.to_datetime(basket_df["timestamp"])
    basket_df.set_index("timestamp", inplace=True)

    if not basket_pips_list:
        final_pips = 0
        peak_pips = 0
        max_drawdown_pips = 0
    else:
        final_pips = basket_pips_list[-1][1]
        peak_pips = max(p[1] for p in basket_pips_list)
        max_drawdown_pips = min(p[1] for p in basket_pips_list)

    major_event = None
    for event in news_events:
        if event.get("impact", "") == "High":
            major_event = event.get("title")
            break
    if not major_event and news_events:
        major_event = news_events[0].get("title")

    return {
        "strategy_name": STRATEGY_NAME,
        "basket_start_date": basket_start_date,
        "basket_end_date": basket_end_date,
        "major_event": major_event or "Unknown Major Event",
        "total_trades": 0,
        "final_profit": 0,
        "final_pips": round(final_pips, 1),
        "peak_pips": round(peak_pips, 1),
        "max_drawdown_pips": round(max_drawdown_pips, 1),
        "key_highlights": "Peak pips early, some mid-cycle retracement.",
        "basket_df": basket_df
    }

def find_top_major_events(news_events, basket_df):
    event_impact = []
    grouped_events = defaultdict(list)

    for event in news_events:
        event_time = pd.to_datetime(event['timestamp'])
        event_minute = event_time.replace(second=0, microsecond=0)
        grouped_events[event_minute].append(event['title'])

    print("\n🔍 [Debug] Analyzing grouped news event clusters:")

    for group_time, titles in grouped_events.items():
        window_start = group_time - timedelta(minutes=60)
        window_end = group_time + timedelta(minutes=60)
        window_data = basket_df[(basket_df.index >= window_start) & (basket_df.index <= window_end)]

        print(f"  - Cluster at {group_time}: {titles}")
        print(f"    Window: {window_start} to {window_end}")
        print(f"    Matching snapshots: {len(window_data)}")

        if not window_data.empty:
            pips_change = window_data['basket_pips'].iloc[-1] - window_data['basket_pips'].iloc[0]
            event_impact.append({
                'titles': titles,
                'time': group_time,
                'abs_change': abs(pips_change),
                'real_change': pips_change
            })
            print(f"    Pips Change: {pips_change:.1f}")

    positive_moves = sorted([e for e in event_impact if e['real_change'] > 0], key=lambda x: x['abs_change'], reverse=True)
    negative_moves = sorted([e for e in event_impact if e['real_change'] < 0], key=lambda x: x['abs_change'], reverse=True)

    top_events = positive_moves[:3] + negative_moves[:3]

    print("\n🏆 [Debug] Top 6 Major Event Clusters by Basket Movement:")
    for idx, event in enumerate(top_events, 1):
        print(f"  {idx}. {event['titles']} | Basket Change: {event['real_change']:.1f} pips (Abs: {event['abs_change']:.1f}) at {event['time']}")

    return top_events


def prepare_prompt(summary):
    major_event_text = ""
    for idx, event in enumerate(summary['major_events'], 1):
        titles = ", ".join(event['titles'])
        move_direction = "up" if event['real_change'] > 0 else "down"
        major_event_text += f"{idx}. {titles} at {event['time']} — Basket moved {event['real_change']:.1f} pips {move_direction}.\n"

    prompt = f"""
You are a professional trading blog writer.
Using the following information, write a detailed and natural-sounding forex trading blog post.
The blog post is a monthly recap of trades by the trading strategy.
Focus on clarity, professionalism, and storytelling. Make it easy to read and concise. 

Add a YAML frontmatter
1. A YAML frontmatter at the top of the file with:
    - author: Amber
    - pubDatetime: Current time in ISO format
    - modDatetime: Same as pubDatetime
    - title: A bold blog title (from the content, no label prefix)
    - slug: A kebab-case version of the title (e.g., "april-9-trade-summary-jpy-reversal")
    - featured: false
    - draft: false
    - tags: forex, skyengine, analysis, algotrading
    - description: A short, natural-sounding 1–2 sentence summary of the day's trading action. Do not repeat the title.

2. After the frontmatter, include the same title again as a bold Markdown heading.


Strategy Name: {summary['strategy_name']}
Basket Start Date: {summary['basket_start_date']}
Basket End Date: {summary['basket_end_date']}

Major Events and Basket Reactions:
{major_event_text}

Total Trades: {summary['total_trades']}
Final Pips: {summary['final_pips']}
Peak Pips: {summary['peak_pips']}
Max Drawdown Pips: {summary['max_drawdown_pips']}
Key Highlights: {summary['key_highlights']}

Structure the post with these sections:
- Setup and Trigger
- Journey of the Trade
- Expiry and Closure
- Reflections and Next Steps
Use a bold Markdown heading for the title. Do not repeat the title inside the body.
Do not wrap the title in quotes or say “Title:”. Format all output as clean markdown. Give me the final output in a downloadable markdown file name "blog_post_monthly.md". Next, after generating the blog post in markdown, generate a second markdown file for twitter caption with filename "twitter_caption_monthly.md" and a third markdown file for instagram caption filenamed "instagram_caption_monthly.md". The tone should curious, exciting and inviting in the captions. Give all 3 markdowns in links that I can click and download.
"""
    return prompt


# === MAIN ===

def main():
    entries = load_all_logs(LOGS_DIR)
    filtered_data = extract_filtered_logs(entries)
    summary = extract_summary(filtered_data)

    # Fetch real closed trades summary
    start_time = summary['basket_start_date'] + "T00:00:00Z"
    end_time = summary['basket_end_date'] + "T23:59:59Z"
    trades_summary = OANDA_CLIENT.fetch_closed_trades_summary(OANDA_ACCOUNT_ID, start_time, end_time)

    # Update summary with real values
    summary['total_trades'] = trades_summary['total_trades']
    summary['final_profit'] = trades_summary['final_profit']

    # Find major event clusters
    top_major_events = find_top_major_events(filtered_data['news_events'], summary['basket_df'])
    summary['major_events'] = top_major_events

    # Generate the blog prompt
    prompt = prepare_prompt(summary)

    # Save the blog prompt
    prompt_file = os.path.join(OUTPUT_DIR, f"blog_prompt_{summary['basket_end_date']}.txt")
    with open(prompt_file, "w") as f:
        f.write(prompt)

    print(f"✅ Blog prompt generated: {prompt_file}")

    # Save the basket pips csv
    basket_csv = os.path.join(OUTPUT_DIR, f"basket_scores_{summary['basket_end_date']}.csv")
    summary['basket_df'].to_csv(basket_csv)
    print(f"✅ Basket scores saved: {basket_csv}")

    # Plotting
    plt.figure(figsize=(12, 6))
    summary['basket_df']["basket_pips"].plot(label="Basket Pips", color="blue")
    plt.title("Basket Pips Over Time")
    plt.xlabel("Time")
    plt.ylabel("Basket Pips")

    peak_time = summary['basket_df']['basket_pips'].idxmax()
    trough_time = summary['basket_df']['basket_pips'].idxmin()
    final_time = summary['basket_df'].index[-1]

    plt.scatter(peak_time, summary['basket_df'].loc[peak_time, 'basket_pips'], color='green', label='Peak', zorder=5)
    plt.scatter(trough_time, summary['basket_df'].loc[trough_time, 'basket_pips'], color='red', label='Trough', zorder=5)
    plt.scatter(final_time, summary['basket_df'].loc[final_time, 'basket_pips'], color='purple', label='Expiry', zorder=5)

    plt.annotate(f"{summary['basket_df'].loc[peak_time, 'basket_pips']:.1f} pips", (peak_time, summary['basket_df'].loc[peak_time, 'basket_pips']),
                 textcoords="offset points", xytext=(0,10), ha='center', fontsize=8, color='green')
    plt.annotate(f"{summary['basket_df'].loc[trough_time, 'basket_pips']:.1f} pips", (trough_time, summary['basket_df'].loc[trough_time, 'basket_pips']),
                 textcoords="offset points", xytext=(0,-15), ha='center', fontsize=8, color='red')
    plt.annotate(f"{summary['basket_df'].loc[final_time, 'basket_pips']:.1f} pips", (final_time, summary['basket_df'].loc[final_time, 'basket_pips']),
                 textcoords="offset points", xytext=(0,10), ha='center', fontsize=8, color='purple')

    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plot_file = os.path.join(OUTPUT_DIR, f"monthly_pips_chart_{summary['basket_end_date']}.png")
    plt.savefig(plot_file)
    print(f"✅ Basket scores plot saved: {plot_file}")



if __name__ == "__main__":
    main()
