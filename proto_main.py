import os
import json
import requests
import pyperclip
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI
from core.formatter import format_markdown
from core.chart_generator import generate_basket_pips_chart
from collections import defaultdict

load_dotenv()
HOME = str(Path.home())
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK")
BLOG_ID = (datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')
LOG_FILE_PATH = f"{HOME}/Documents/MacTrader/SkyeFX/SkyEngine/logs/blog_logs_{BLOG_ID}.log"
SAVE_DIRECTORY = f"{HOME}/Documents/MacTrader/Murmur/Core/proto_blogs/"
DAILY_SNAPSHOT_PROMPT = f"{HOME}/Documents/MacTrader/Murmur/Core/prompts/daily_snapshot_prompt.txt"
BASKET_PIPS_DIRECTORY = f"{HOME}/Documents/MacTrader/Murmur/Shell/astro-paper/public/assets/"

client = OpenAI(api_key=OPENAI_API_KEY)

def generate_post(prompt):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.7
    )

    message = response.choices[0].message.content

    # Print token usage
    if response.usage:
        print(f"🧠 Token usage:")
        print(f"   → Prompt tokens:     {response.usage.prompt_tokens}")
        print(f"   → Completion tokens: {response.usage.completion_tokens}")
        print(f"   → Total tokens:      {response.usage.total_tokens}")

    return message


def read_log_file(filepath):
    with open(filepath, 'r') as file:
        return [json.loads(line) for line in file if line.strip()]

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
    # Helper: normalize to YYYY-MM-DDTHH:MM (truncate to the minute)
    def get_minute_bucket(ts):
        dt = datetime.fromisoformat(ts)
        return dt.replace(second=0, microsecond=0).isoformat()
    # Group snapshots into baskets using the minute
    basket_groups = defaultdict(list)
    for snap in snapshots:
        minute_key = get_minute_bucket(snap["timestamp"])
        basket_groups[minute_key].append(snap)
    # Compute total basket pips for each group
    basket_scores = {}  # timestamp → total basket pips
    for ts, snaps in basket_groups.items():
        total_pips = sum(s["pips"] for s in snaps if "pips" in s)
        basket_scores[ts] = total_pips
    # Identify highest and lowest basket totals
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
        #logic test
        if total_pips < lowest_basket_pips:
            lowest_basket_pips = total_pips
            lowest_basket_ts = [ts]
        elif total_pips == lowest_basket_pips:
            lowest_basket_ts.append(ts)
    # Gather snapshots for those baskets
    highest_basket = [snap for ts in highest_basket_ts for snap in basket_groups[ts]]
    lowest_basket = [snap for ts in lowest_basket_ts for snap in basket_groups[ts]]
    # Inject summary entries
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
    # Snapshots ±1 hour around news events
    related_snapshots = []
    for event in news_events:
        event_time = datetime.fromisoformat(event["timestamp"])
        window_start = event_time - timedelta(hours=1)
        window_end = event_time + timedelta(hours=1)
        #loop
        for ts, snaps in basket_groups.items():
            basket_time = datetime.fromisoformat(ts)
            if window_start <= basket_time <= window_end:
                related_snapshots.extend(snaps)
    # First and last basket of the day
    sorted_basket_times = sorted(basket_groups.keys())
    first_basket = basket_groups[sorted_basket_times[0]] if sorted_basket_times else []
    last_basket = basket_groups[sorted_basket_times[-1]] if sorted_basket_times else []
    # Combine and deduplicate
    combined_logs = (
        news_events +
        related_snapshots +
        first_basket +
        last_basket +
        highest_basket +
        lowest_basket +
        summary_entries
    )
    unique_logs = {json.dumps(log, sort_keys=True): log for log in combined_logs}
    sorted_logs = sorted(unique_logs.values(), key=lambda x: x["timestamp"])
    return "\n".join([json.dumps(log) for log in sorted_logs])




def create_prompt_from_log(log_data):
    with open(DAILY_SNAPSHOT_PROMPT, "r") as file:
        prompt_raw = file.read()
    return f"""{prompt_raw}\n\n{log_data}"""

def save_to_markdown(content, save_dir="/your/custom/path/here"):
    os.makedirs(save_dir, exist_ok=True)
    formatted = format_markdown(content)
    filename = datetime.now().strftime("trade_summary_%Y-%m-%d.md")
    filepath = os.path.join(save_dir, filename)
    with open(filepath, "w") as f:
        f.write(formatted)
    return filepath

def notify_slack(filepath):
    filename = os.path.basename(filepath)
    payload = {
        "text": f":memo: *New Trade Summary Generated!* `{filename}` has been saved.\nLocation: `{filepath}`"
    }
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    return response.status_code == 200

if __name__ == "__main__":
    log_data = read_log_file(LOG_FILE_PATH)
    filtered_log_text = extract_filtered_logs(log_data)
    prompt = create_prompt_from_log(filtered_log_text)
    pyperclip.copy(prompt)
    print(f"This is the generated prompt\n\n{prompt}\n\n")
    generate_basket_pips_chart(LOG_FILE_PATH,f"{BASKET_PIPS_DIRECTORY}/pips_chart_{BLOG_ID}.png")
    # output = generate_post(prompt)
    # saved_path = save_to_markdown(output, save_dir=SAVE_DIRECTORY)

    # print(f"✅ Summary saved to: {saved_path}")
    # if notify_slack(saved_path):
    #     print("📨 Slack notification sent.")
    # else:
    #     print("❌ Failed to send Slack notification.")