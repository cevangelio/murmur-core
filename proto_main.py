import os
import json
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI
from core.formatter import format_markdown

load_dotenv()
HOME = str(Path.home())
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK")
LOG_FILE_PATH = f"{HOME}/Documents/MacTrader/SkyeFX/SkyEngine/logs/blog_logs_{(datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')}.log"
SAVE_DIRECTORY = f"{HOME}/Documents/MacTrader/Murmur/Core/proto_blogs/"
DAILY_SNAPSHOT_PROMPT = f"{HOME}/Documents/MacTrader/Murmur/Core/prompts/daily_snapshot_prompt.txt"

client = OpenAI(api_key=OPENAI_API_KEY)

def generate_post(prompt):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.7
    )
    return response.choices[0].message.content

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

    snapshot_times = [datetime.fromisoformat(s["timestamp"]) for s in snapshots]
    all_timestamps = []

    for event in news_events:
        event_time = datetime.fromisoformat(event["timestamp"])
        window_start = event_time - timedelta(hours=1)
        window_end = event_time + timedelta(hours=1)

        related_snapshots = [
            s for s in snapshots
            if window_start <= datetime.fromisoformat(s["timestamp"]) <= window_end
        ]
        all_timestamps.extend(related_snapshots)

    if snapshots:
        all_timestamps.append(min(snapshots, key=lambda x: x["timestamp"]))
        all_timestamps.append(max(snapshots, key=lambda x: x["timestamp"]))

    # Remove duplicates
    unique_logs = {json.dumps(log, sort_keys=True): log for log in news_events + all_timestamps}
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
    output = generate_post(prompt)
    saved_path = save_to_markdown(output, save_dir=SAVE_DIRECTORY)

    print(f"✅ Summary saved to: {saved_path}")
    if notify_slack(saved_path):
        print("📨 Slack notification sent.")
    else:
        print("❌ Failed to send Slack notification.")