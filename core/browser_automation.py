import undetected_chromedriver as uc
import time
import os
import shutil
import pyperclip
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def run_chatgpt_blog_prompt(prompt: str,
                             profile_dir: str = "~/Library/Application Support/BraveSoftware/Brave-Browser/Default",
                             brave_binary: str = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                             download_dir: str = "~/Downloads",
                             blog_dest: str = "~/Documents/MacTrader/Blogs",
                             wait_time: int = 60):
    """
    Launches Brave, navigates to ChatGPT, clicks Project Murmur, pastes a prompt, and waits for markdown download.
    """
    profile_dir = os.path.expanduser(profile_dir)
    brave_binary = os.path.expanduser(brave_binary)
    download_dir = os.path.expanduser(download_dir)
    blog_dest = os.path.expanduser(blog_dest)

    # Copy prompt to clipboard
    pyperclip.copy(prompt)

    options = uc.ChromeOptions()
    options.binary_location = brave_binary
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = uc.Chrome(options=options, headless=False, use_subprocess=True)

    try:
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

        # Wait for markdown to finish generating and be downloaded
        print(f"⏳ Waiting {wait_time} seconds for response + download...")
        time.sleep(wait_time)

        # Move downloaded markdown file
        move_latest_markdown(download_dir, blog_dest)

    finally:
        driver.quit()


def move_latest_markdown(download_dir, blog_dest):
    files = [f for f in os.listdir(download_dir) if f.endswith(".md")]
    if not files:
        print("⚠️ No markdown files found.")
        return
    latest = max(files, key=lambda f: os.path.getctime(os.path.join(download_dir, f)))
    src = os.path.join(download_dir, latest)
    dest = os.path.join(blog_dest, latest)
    shutil.move(src, dest)
    print(f"✅ Moved: {latest} → {dest}")
