import os
import json
import requests
import pyperclip
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from openai import OpenAI
from core.formatter import format_markdown
from tools.mover import rename_and_move_blog_file
from core.post_saver import git_commit_and_push
from core.browser_automation import (
    create_driver,
    run_chatgpt_blog_prompt,
    click_markdown_links,
)
import time

load_dotenv()
HOME = str(Path.home())
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK")

SIGNALS_FILE = f"{HOME}/Documents/MacTrader/EchoAPI/signals-amber.json"
PROMPT_TEMPLATE = f"{HOME}/Documents/MacTrader/Murmur/Core/prompts/signal_gen_prompt.txt"
BLOG_DIRECTORY = f"{HOME}/Documents/MacTrader/Murmur/Shell/astro-paper/"
BLOG_COMPLETED_DIRECTORY = f"{BLOG_DIRECTORY}/src/data/blog/"
MARKDOWN_BLOG_FILE = f"{HOME}/Downloads/blog_post.md"

client = OpenAI(api_key=OPENAI_API_KEY)

def should_run_blog():
    try:
        with open(SIGNALS_FILE, 'r') as f:
            signals_data = json.load(f)
        signal_date_str = signals_data.get("date")
        if not signal_date_str:
            print("❌ No 'date' found in signal file.")
            return False

        signal_date = datetime.strptime(signal_date_str, "%Y-%m-%d").date()
        today = datetime.today().date()

        # Only run if signal is fresh (e.g., within past 4 days)
        if (today - signal_date).days <= 4:
            print(f"✅ Fresh signal found for {signal_date_str}. Proceeding.")
            return True
        else:
            print(f"ℹ️ Signal is too old ({signal_date_str}). Skipping blog generation.")
            return False
    except Exception as e:
        print(f"⚠️ Error checking signal file: {e}")
        return False

def load_signals():
    with open(SIGNALS_FILE, 'r') as f:
        return json.load(f)

def load_prompt_template():
    with open(PROMPT_TEMPLATE, 'r') as f:
        return f.read()

def build_prompt(signal_data):
    prompt = load_prompt_template()
    return f"{prompt.strip()}\n\n{json.dumps(signal_data, indent=2)}"

def delete_old_md_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)
        print("Deleted old markdown file.")
    else:
        print("No previous markdown file found.")

def notify_slack(filepath):
    filename = os.path.basename(filepath)
    payload = {
        "text": f":crystal_ball: *New Signal Brief Generated!* `{filename}` has been saved.\nLocation: `{filepath}`"
    }
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    return response.status_code == 200

if __name__ == "__main__":
    if not should_run_blog():
        exit(0)

    signal_data = load_signals()
    prompt = build_prompt(signal_data)
    pyperclip.copy(prompt)
    print("✏️ Prompt copied to clipboard. You can now paste it into ChatGPT browser.")
    print(f"Prompt preview:\n\n{prompt}\n\n")
    delete_old_md_file(MARKDOWN_BLOG_FILE)
    all_md_links = ["blog_post.md"]
    driver = create_driver()
    try:
        run_chatgpt_blog_prompt(prompt, driver, wait_time=60)
        click_markdown_links(driver, all_md_links)
    finally:
        driver.quit()

    date_str = datetime.now().strftime("%Y-%m-%d")
    rename_and_move_blog_file(f"{HOME}/Downloads/", BLOG_COMPLETED_DIRECTORY, "signal_summary")
    blog_path = f"{BLOG_COMPLETED_DIRECTORY}/signal_summary_{date_str}.md"
    git_commit_and_push(BLOG_DIRECTORY, [blog_path])
    notify_slack(blog_path)
