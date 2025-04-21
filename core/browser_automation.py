import undetected_chromedriver as uc
import time
import os
import shutil
import pyperclip
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

HOME = str(Path.home())
PROFILE_DIR = "~/Library/Application Support/BraveSoftware/Brave-Browser/Default"
BRAVE_BINARY = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
DOWNLOAD_DIR = "~/Downloads"
BLOG_DIR = f"{HOME}/Documents/MacTrader/Murmur/Shell/astro-paper/src/data/blog/"

def create_driver(profile_dir=PROFILE_DIR, brave_binary=BRAVE_BINARY):
    """
    Creates and returns a Selenium driver instance using undetected-chromedriver.
    """
    profile_dir = os.path.expanduser(profile_dir)
    brave_binary = os.path.expanduser(brave_binary)

    options = uc.ChromeOptions()
    options.binary_location = brave_binary
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    return uc.Chrome(options=options, headless=False, use_subprocess=True)


def run_chatgpt_blog_prompt(prompt: str,
                             driver,
                             download_dir: str = DOWNLOAD_DIR,
                             blog_dest: str = BLOG_DIR,
                             wait_time: int = 60):
    """
    Navigates to ChatGPT, clicks Project Murmur, pastes a prompt, and waits.
    """
    download_dir = os.path.expanduser(download_dir)
    blog_dest = os.path.expanduser(blog_dest)

    pyperclip.copy(prompt)

    driver.get("https://chat.openai.com/")
    wait = WebDriverWait(driver, 30)

    # Click on the Project Murmur sidebar link
    project_murmur_link = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//a[@title='Project Murmur']")
    ))
    project_murmur_link.click()
    print("✅ Clicked on Project Murmur")

    # Let the chat load
    time.sleep(10)

    # Paste from clipboard + hit ENTER
    actions = ActionChains(driver)
    actions.key_down(Keys.COMMAND).send_keys("v").key_up(Keys.COMMAND).send_keys(Keys.ENTER).perform()
    print("✅ Prompt pasted and submitted!")

    # Wait for markdown to finish generating
    print(f"⏳ Waiting {wait_time} seconds for response to generate...")
    time.sleep(wait_time)


def click_markdown_links(driver, keywords, wait_after_each=2):
    wait = WebDriverWait(driver, 20)

    try:
        all_links = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//a[@class='cursor-pointer']")))
    except Exception as e:
        print("❌ Could not find any markdown links.")
        return

    matched = 0
    for link in all_links:
        try:
            link_text = link.text.strip().lower()
            if any(keyword.lower() in link_text for keyword in keywords):
                print(f"🔗 Clicking: {link_text}")
                driver.execute_script("arguments[0].click();", link)
                matched += 1
                time.sleep(wait_after_each)
        except Exception as e:
            print(f"⚠️ Error clicking a link: {e}")

    if matched == 0:
        print("⚠️ No matching markdown download links were clicked.")
    else:
        print(f"✅ Clicked {matched} download link(s).")



def move_latest_markdown(download_dir=DOWNLOAD_DIR, blog_dest=BLOG_DIR):
    download_dir = os.path.expanduser(download_dir)
    blog_dest = os.path.expanduser(blog_dest)

    files = [f for f in os.listdir(download_dir) if f.endswith(".md")]
    if not files:
        print("⚠️ No markdown files found.")
        return
    latest = max(files, key=lambda f: os.path.getctime(os.path.join(download_dir, f)))
    src = os.path.join(download_dir, latest)
    dest = os.path.join(blog_dest, latest)
    shutil.move(src, dest)
    print(f"✅ Moved: {latest} → {dest}")
