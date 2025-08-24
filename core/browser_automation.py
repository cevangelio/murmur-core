# core/browser_automation.py
# -*- coding: utf-8 -*-
"""
Browser automation helpers for ChatGPT workflows (macOS).

Features
- Profile modes:
  - "clone": clones your signed-in Brave/Chrome profile to a temp dir (recommended; works even if your browser is open)
  - "persistent": uses your actual profile dir (browser must be CLOSED)
  - "temp": blank temp profile (no cookies)
- Works with Brave (default) or Chrome.
- Defensive ChatGPT composer detection (new + legacy domains), popup dismissal.
- Back-compat: move_latest_markdown(download_dir, target_path).

Usage
    driver = create_driver(
        profile_mode="clone",        # or "persistent" / "temp"
        use_brave=True,              # False to use Chrome
        profile_directory="Default", # e.g., "Default", "Profile 1"
        headless=False
    )
    try:
        run_chatgpt_blog_prompt(prompt, driver, wait_time=60)
        click_markdown_links(driver, ["blog_post.md"])
    finally:
        tmp = getattr(driver, "_tmp_profile_dir", None)
        driver.quit()
        if tmp and os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
"""

import os
import time
import shutil
import tempfile
import random
import platform
from pathlib import Path
from typing import List, Optional

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    StaleElementReferenceException,
    NoSuchElementException,
)

HOME = str(Path.home())

# Preferred browser binaries (Brave first, then Chrome)
BRAVE_BINARY = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


# ────────────────────────────────────────────────────────────────────────────────
# Path helpers (macOS)
# ────────────────────────────────────────────────────────────────────────────────

def _assert_macos():
    if platform.system() != "Darwin":
        raise RuntimeError("This module assumes macOS paths. Adjust for your OS if needed.")

def _profile_root(use_brave: bool) -> str:
    if use_brave:
        return f"{HOME}/Library/Application Support/BraveSoftware/Brave-Browser"
    return f"{HOME}/Library/Application Support/Google/Chrome"

def _browser_binary(use_brave: bool) -> str:
    return BRAVE_BINARY if use_brave else CHROME_BINARY


# ────────────────────────────────────────────────────────────────────────────────
# Profile clone (works even when the real browser is open)
# ────────────────────────────────────────────────────────────────────────────────

def _clone_profile_to_temp(use_brave: bool, profile_directory: str) -> str:
    """
    Make a lightweight clone of an existing profile to a temp user-data-dir.
    Returns the temp user-data-dir path that contains the cloned Profile folder.
    """
    src_root = _profile_root(use_brave)                       # e.g., .../Brave-Browser
    src_profile = os.path.join(src_root, profile_directory)   # e.g., .../Brave-Browser/Default

    if not os.path.isdir(src_profile):
        raise FileNotFoundError(f"Profile not found: {src_profile}")

    tmp_root = tempfile.mkdtemp(prefix="uc-profclone-")       # used as --user-data-dir
    dst_profile = os.path.join(tmp_root, profile_directory)
    os.makedirs(dst_profile, exist_ok=True)

    # Copy small root file that stores channel/features (helps Chromium init)
    for fname in ("Local State",):
        s = os.path.join(src_root, fname)
        if os.path.exists(s):
            try:
                shutil.copy2(s, os.path.join(tmp_root, fname))
            except Exception:
                pass

    # Copy key state from the profile folder (avoid caches to keep it fast)
    must_copy = [
        "Cookies", "Cookies-journal",
        "Network",                 # includes TransportSecurity, etc.
        "Preferences",
        "Secure Preferences",
        "History", "History Provider Cache",
        "Visited Links",
        "Login Data", "Login Data-journal",
        "Login Data For Account", "Login Data For Account-journal",
        "Web Data",
        "Shortcuts", "Top Sites",
        "Sync Data", "Sync App Settings",
        "Extensions",
        "IndexedDB", "Local Storage", "Session Storage",
        "Service Worker",
    ]

    for name in must_copy:
        src = os.path.join(src_profile, name)
        dst = os.path.join(dst_profile, name)
        if os.path.isdir(src):
            try:
                shutil.copytree(src, dst, dirs_exist_ok=True)
            except Exception:
                pass
        elif os.path.isfile(src):
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            except Exception:
                pass

    print(f"[info] Cloned profile '{profile_directory}' from '{src_root}' → '{tmp_root}'")
    return tmp_root


# ────────────────────────────────────────────────────────────────────────────────
# Driver creation
# ────────────────────────────────────────────────────────────────────────────────

def create_driver(
    *,
    profile_mode: str = "clone",        # "clone" (recommended), "persistent", or "temp"
    use_brave: bool = True,
    profile_directory: str = "Default", # e.g., "Default", "Profile 1", "Profile 2"
    headless: bool = False
):
    """
    Launch undetected-chromedriver with:
      - profile_mode="clone": temp copy of your real profile (keeps cookies, works while browser is open)
      - profile_mode="persistent": live profile (browser must be CLOSED; reuses cookies in-place)
      - profile_mode="temp": blank temp profile (no cookies)
    """
    _assert_macos()

    binary = _browser_binary(use_brave)

    if profile_mode == "temp":
        user_data_dir = tempfile.mkdtemp(prefix="uc-proftemp-")
        extra_profile_arg = None

    elif profile_mode == "persistent":
        root = _profile_root(use_brave)
        if not os.path.isdir(os.path.join(root, profile_directory)):
            raise FileNotFoundError(f"Profile not found: {os.path.join(root, profile_directory)}")
        user_data_dir = root
        extra_profile_arg = f"--profile-directory={profile_directory}"
        print(f"[info] Using PERSISTENT profile: {user_data_dir} ({profile_directory})  "
              f"[Make sure {('Brave' if use_brave else 'Chrome')} is fully closed]")

    elif profile_mode == "clone":
        user_data_dir = _clone_profile_to_temp(use_brave, profile_directory)
        extra_profile_arg = f"--profile-directory={profile_directory}"

    else:
        raise ValueError("profile_mode must be 'clone', 'persistent', or 'temp'")

    dbg_port = random.randint(49152, 65535)
    opts = uc.ChromeOptions()

    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1400,1000")

    # Robust, minimal flags
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--disable-features=Translate,BackForwardCache,AutomationControlled")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--start-maximized")
    opts.add_argument(f"--remote-debugging-port={dbg_port}")
    opts.add_argument(f"--user-data-dir={user_data_dir}")
    if extra_profile_arg:
        opts.add_argument(extra_profile_arg)

    if os.path.exists(binary):
        opts.binary_location = binary

    print(f"[info] Launching UC with binary: {binary if os.path.exists(binary) else 'system default'}")
    print(f"[info] --user-data-dir: {user_data_dir}")
    if extra_profile_arg:
        print(f"[info] {extra_profile_arg}")

    driver = uc.Chrome(options=opts, use_subprocess=True, suppress_welcome=True)
    # For clone/temp modes, mark for cleanup by caller
    if profile_mode in ("clone", "temp"):
        driver._tmp_profile_dir = user_data_dir
    return driver


# ────────────────────────────────────────────────────────────────────────────────
# DOM/composer readiness
# ────────────────────────────────────────────────────────────────────────────────

_COMPOSER_SELECTORS = [
    # Most common
    'textarea[data-testid="composer-textarea"]',
    'div[contenteditable="true"][data-testid="composer-textarea"]',
    # Other known variants
    'textarea[placeholder*="Message"]',
    'textarea[placeholder*="Send a message"]',
    'textarea#prompt-textarea',
    'div[contenteditable="true"][aria-label*="Message"]',
    'div[contenteditable="true"][role="textbox"]',
    # Generic fallbacks (last resort)
    '[role="textbox"][contenteditable="true"]',
    '[data-testid="composer:input"]',
]

_CLICK_PATHS = [
    # New chat entry points
    ('css', 'button[data-testid="new-chat-button"]'),
    ('xpath', "//button[contains(., 'New chat')]"),
    ('xpath', "//a[contains(., 'New chat')]"),
    ('xpath', "//button[contains(., 'New conversation')]"),
    ('xpath', "//a[contains(., 'New conversation')]"),
    # Switch to the Chat tab from Explore/Apps
    ('xpath', "//a[.//span[contains(., 'Chat')]]"),
    ('xpath', "//button[.//span[contains(., 'Chat')]]"),
]

_DISMISS_BUTTON_XPATHS = [
    "//button[normalize-space(.)='Got it']",
    "//button[normalize-space(.)='OK']",
    "//button[normalize-space(.)='Close']",
    "//button[normalize-space(.)='Continue']",
    "//button[contains(., 'Skip')]",
    "//button[contains(., 'Start chatting')]",
    "//button[contains(., 'Continue to chat')]",
]

_ACCEPT_COOKIES_XPATHS = [
    "//button[contains(., 'Accept all')]",
    "//button[contains(., 'Accept') and contains(., 'cookies')]",
    "//button[contains(., 'Allow all')]",
]

def _force_focus_any_textbox_and_type(driver, text: str) -> bool:
    """
    Fallback when we can't see the classic composer:
    - Try known composer selectors
    - Try clicking the 'Ask anything' omnibox (several variants)
    - Finally click the visual center of the page and type into the active element
    Returns True if keys were sent to a focused editable field.
    """
    # 1) Known composer selectors
    try:
        for sel in _COMPOSER_SELECTORS:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    el.click()
                    el.send_keys(text)
                    return True
            except Exception:
                continue
    except Exception:
        pass

    # 2) Click omnibox or any element that mentions it
    try:
        if _click_omnibox_if_present(driver):
            # After clicking, try active element directly
            try:
                driver.switch_to.active_element.send_keys(text)
                return True
            except Exception:
                pass
        # Extra omnibox fallbacks
        xpaths = [
            "//*[normalize-space()='Ask anything']",
            "//*[contains(., 'Ask anything')][self::div or self::button or self::span]",
        ]
        for xp in xpaths:
            try:
                el = driver.find_element(By.XPATH, xp)
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                time.sleep(0.2)
                try:
                    driver.switch_to.active_element.send_keys(text)
                    return True
                except Exception:
                    pass
            except Exception:
                continue
    except Exception:
        pass

    # 3) Brutal fallback: click the visual center of the page, then type
    try:
        rect = driver.execute_script("""
            const el = document.querySelector('main') || document.body;
            const r = el.getBoundingClientRect();
            return {x: Math.floor((r.left + r.right)/2), y: Math.floor((r.top + r.bottom)/2)};
        """)
        if rect and isinstance(rect, dict):
            # Click at elementFromPoint center
            driver.execute_script("""
                const evt = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
                const el = document.elementFromPoint(arguments[0], arguments[1]);
                if (el) el.dispatchEvent(evt);
            """, rect["x"], rect["y"])
            time.sleep(0.2)
            ae = driver.switch_to.active_element
            try:
                ae.send_keys(text)
                return True
            except Exception:
                pass
    except Exception:
        pass

    return False

def _wait_dom_stable(driver, max_wait=12, poll=0.4):
    end = time.time() + max_wait
    last_len = 0
    stable_ticks = 0
    while time.time() < end:
        try:
            ready = driver.execute_script("return document.readyState") == "complete"
            text = driver.execute_script("return document.body ? document.body.innerText : ''") or ""
            if ready:
                if len(text) < 150:
                    stable_ticks = 0
                else:
                    if len(text) == last_len:
                        stable_ticks += 1
                    else:
                        stable_ticks = 0
                    last_len = len(text)
                    if stable_ticks >= 3:
                        return True
        except StaleElementReferenceException:
            pass
        time.sleep(poll)
    return False

def _dismiss_popups(driver):
    # Cookie banners
    for xp in _ACCEPT_COOKIES_XPATHS:
        try:
            driver.find_element(By.XPATH, xp).click()
            time.sleep(0.3)
        except Exception:
            pass
    # Generic modals / tours
    for xp in _DISMISS_BUTTON_XPATHS:
        try:
            driver.find_element(By.XPATH, xp).click()
            time.sleep(0.3)
        except Exception:
            pass

def _find_any(driver, selectors, timeout=0):
    if timeout > 0:
        end = time.time() + timeout
        while time.time() < end:
            for sel in selectors:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                    if el:
                        return el
                except Exception:
                    continue
            time.sleep(0.2)
        return None
    else:
        for sel in selectors:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if el:
                    return el
            except Exception:
                continue
        return None
    
def _click_omnibox_if_present(driver) -> bool:
    """
    On the new ChatGPT home, the centered 'Ask anything' omnibox hides the composer
    until clicked. This tries several selectors and clicks it if visible.
    Returns True if we clicked something that looks like the omnibox.
    """
    xpaths = [
        # Actual input/textarea with placeholder/aria-label
        "//input[contains(@placeholder,'Ask anything') or contains(@aria-label,'Ask anything')]",
        "//textarea[contains(@placeholder,'Ask anything') or contains(@aria-label,'Ask anything')]",
        "//div[contains(@aria-label,'Ask anything')]",
        # Text node variant – click the nearest clickable container
        "//*[normalize-space()='Ask anything']/ancestor::*[self::div or self::button][1]",
        "//*[contains(., 'Ask anything') and (self::button or self::a)]",
    ]
    for xp in xpaths:
        try:
            el = driver.find_element(By.XPATH, xp)
            if el.is_displayed():
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                except Exception:
                    pass
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                time.sleep(0.4)
                return True
        except Exception:
            continue
    return False

def _open_project_and_new_chat(driver, project_url: str, project_name: str = "Project Murmur", tries: int = 3) -> bool:
    """
    Navigate into the project space and open a new chat there.
    If the explicit 'New chat in …' button is not clickable fast enough,
    fall back to focusing the omnibox/active element and typing.
    """
    def on_project_page() -> bool:
        try:
            if "/g/" in driver.current_url and "/project" in driver.current_url:
                return True
        except Exception:
            pass
        checks = [
            f"//h1[contains(., '{project_name}') or contains(@title, '{project_name}')]",
            f"//header//*[contains(., '{project_name}')]",
        ]
        for xp in checks:
            try:
                if driver.find_elements(By.XPATH, xp):
                    return True
            except Exception:
                pass
        return False

    # 1) Go directly to project
    driver.get(project_url)
    _wait_dom_stable(driver, max_wait=10)
    _dismiss_popups(driver)

    # 2) If we didn’t land inside, click sidebar item
    if not on_project_page():
        for xp in (
            f"//nav//a[.//span[contains(., '{project_name}')]]",
            f"//nav//a[contains(., '{project_name}')]",
        ):
            try:
                el = driver.find_element(By.XPATH, xp)
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                _wait_dom_stable(driver, max_wait=6)
                _dismiss_popups(driver)
                break
            except Exception:
                continue

    # 3) Try explicit project-scoped "New chat" controls quickly (before redirects)
    new_chat_xps = [
        f"//button[contains(., 'New chat in') and contains(., '{project_name}')]",
        "//button[contains(., 'New chat in')]",
        f"//a[contains(., 'New chat in') and contains(., '{project_name}')]",
        "//a[contains(., 'New chat in')]",
        "//button[normalize-space(.)='New chat']",
        "//a[normalize-space(.)='New chat']",
        "//*[@aria-label and contains(@aria-label, 'New chat')]",
    ]
    for _ in range(tries):
        for xp in new_chat_xps:
            try:
                el = driver.find_element(By.XPATH, xp)
                if not el.is_displayed():
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                time.sleep(0.5)
                if _ensure_composer_ready(driver):
                    return True
            except Exception:
                continue
        _dismiss_popups(driver)
        time.sleep(0.3)

    # 4) Fallback: just focus *any* textbox on screen and type (omnibox → composer)
    return _force_focus_any_textbox_and_type(driver, "") or _composer_present(driver)

def _click_new_chat_if_present(driver):
    # 1) explicit data-testid
    try:
        el = driver.find_element(By.CSS_SELECTOR, 'button[data-testid="new-chat-button"]')
        el.click()
        time.sleep(0.4)
        return True
    except Exception:
        pass
    # 2) textual buttons/links
    for text in ("New chat", "New conversation"):
        try:
            el = driver.find_element(By.XPATH, f"//button[contains(., '{text}')]|//a[contains(., '{text}')]")
            el.click()
            time.sleep(0.4)
            return True
        except Exception:
            continue
    return False

def _click_any(driver, paths):
    for kind, locator in paths:
        try:
            if kind == 'css':
                driver.find_element(By.CSS_SELECTOR, locator).click()
            else:
                driver.find_element(By.XPATH, locator).click()
            time.sleep(0.4)
            return True
        except Exception:
            continue
    return False

def _composer_present(driver):
    return _find_any(driver, _COMPOSER_SELECTORS, timeout=0) is not None

def _ensure_composer_ready(driver, tries=4):
    """
    Make the composer appear by:
      1) clicking the 'Ask anything' omnibox (new home UI)
      2) dismissing popups
      3) clicking Chat/New chat
      4) light reload nudges
    """
    if _composer_present(driver):
        return True

    for _ in range(tries):
        # New home screen path
        if _click_omnibox_if_present(driver) and _composer_present(driver):
            return True

        _dismiss_popups(driver)
        if _composer_present(driver):
            return True

        # Sidebar buttons
        if _click_any(driver, _CLICK_PATHS) and _composer_present(driver):
            return True

        # Nudge
        try:
            driver.execute_script("window.scrollTo(0, 0)")
        except Exception:
            pass
        time.sleep(0.5)

    return _composer_present(driver)


def _focus_and_type(driver, text: str, timeout=20):
    last_err = None
    end = time.time() + timeout
    while time.time() < end:
        for sel in _COMPOSER_SELECTORS:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                el.click()
                el.send_keys(text)
                return
            except Exception as e:
                last_err = e
        time.sleep(0.2)
    raise RuntimeError(f"Could not find ChatGPT composer. Last error: {last_err}")

def extract_last_response_markdown(driver, wait_seconds: int = 60) -> str:
    """
    Returns the Markdown of the most recent assistant message.
    Strategy:
      1) If there's a code block (pre > code), copy its textContent (already raw).
      2) Else, take the assistant message innerHTML and convert to Markdown.
    """
    end = time.time() + wait_seconds

    assistant_selectors = [
        '[data-message-author-role="assistant"]',
        'div[data-testid="conversation-turn"][data-turn-author="assistant"]',
    ]

    last_el = None
    while time.time() < end and not last_el:
        nodes = []
        for sel in assistant_selectors:
            try:
                nodes.extend(driver.find_elements(By.CSS_SELECTOR, sel))
            except Exception:
                pass
        nodes = [n for n in nodes if n.is_displayed()]
        if nodes:
            last_el = nodes[-1]
            break
        time.sleep(0.25)

    if not last_el:
        raise RuntimeError("No assistant response found in chat.")

    # 1) Prefer a code block if present (raw markdown-friendly)
    try:
        code_blocks = last_el.find_elements(By.CSS_SELECTOR, "pre code")
        code_blocks = [c for c in code_blocks if c.is_displayed()]
        if code_blocks:
            raw = driver.execute_script("return arguments[0].textContent;", code_blocks[-1]) or ""
            raw = raw.strip()
            if raw:
                return raw
    except Exception:
        pass

    # 2) Fallback: convert innerHTML → Markdown
    inner_html = driver.execute_script("return arguments[0].innerHTML;", last_el) or ""
    inner_html = inner_html.strip()
    if not inner_html:
        # last fallback: innerText (may lose some formatting but better than nothing)
        text = driver.execute_script("return arguments[0].innerText;", last_el) or ""
        return text.strip()

    # Configure markdownify: ATX headings, keep strong/emphasis, allow tables
    # markdownify has basic table support; this config keeps structure readable
    markdown = md(
        inner_html,
        heading_style="ATX",
        bullets="*",
        strip=["span"],
        convert=["table", "thead", "tbody", "tr", "th", "td"]
    ).strip()

    return markdown

def extract_last_fenced_markdown(driver, timeout: int = 120) -> str:
    """
    Waits for the latest assistant message to contain a fenced code block
    and returns its raw text. Prefers ```markdown fences.
    """
    end = time.time() + timeout
    last_turn = None

    # 1) Wait for an assistant turn to appear
    assistant_selectors = [
        '[data-message-author-role="assistant"]',
        'div[data-testid="conversation-turn"][data-turn-author="assistant"]',
    ]
    while time.time() < end and last_turn is None:
        nodes = []
        for sel in assistant_selectors:
            try:
                nodes.extend(driver.find_elements(By.CSS_SELECTOR, sel))
            except Exception:
                pass
        nodes = [n for n in nodes if n.is_displayed()]
        if nodes:
            last_turn = nodes[-1]
            break
        time.sleep(0.2)

    if last_turn is None:
        raise RuntimeError("No assistant turn found.")

    # 2) Inside the last assistant turn, wait for at least one code block
    def _has_code_block(_):
        try:
            cbs = last_turn.find_elements(By.CSS_SELECTOR, "pre code")
            cbs = [c for c in cbs if c.is_displayed()]
            return cbs if cbs else False
        except Exception:
            return False

    cbs = WebDriverWait(driver, timeout=max(1, int(end - time.time()))).until(_has_code_block)

    # 3) Prefer a 'markdown' fence/codeblock if identifiable
    def _lang_of(code_el):
        # Try common attributes/classnames ChatGPT uses
        lang = (code_el.get_attribute("data-language") or "").strip().lower()
        if not lang:
            classes = (code_el.get_attribute("class") or "").lower()
            # e.g., "language-markdown", "lang-markdown"
            for token in classes.split():
                if "markdown" in token:
                    return "markdown"
        return lang

    chosen = None
    for cb in reversed(cbs):
        lang = _lang_of(cb)
        if lang == "markdown":
            chosen = cb
            break
    if chosen is None:
        chosen = cbs[-1]  # fallback to the last visible code block

    # 4) Grab raw textContent (not innerText)
    raw = driver.execute_script("return arguments[0].textContent;", chosen) or ""
    raw = raw.strip()
    if not raw:
        raise RuntimeError("Code block found but empty.")
    return raw


# ────────────────────────────────────────────────────────────────────────────────
# ChatGPT actions
# ────────────────────────────────────────────────────────────────────────────────

def run_chatgpt_blog_prompt(
    prompt: str,
    driver,
    wait_time: int = 60,
    project_url: Optional[str] = None,
):
    """
    Open the project page, move focus into the New Chat box (via TAB),
    paste the prompt, press Enter, and wait for the response.
    """
    if not project_url:
        raise ValueError("project_url must be provided for project-scoped chat")

    # 1. Navigate to project page
    driver.get(project_url)
    _wait_dom_stable(driver, max_wait=10)
    time.sleep(1.0)

    # 2. Press TAB to shift focus from URL bar → composer
    # ActionChains(driver).send_keys(Keys.TAB).perform()
    # time.sleep(0.5)

    # 3. Inject the text into the active element
    js_code = """
    const el = document.activeElement;
    if (el && (el.tagName === 'TEXTAREA' || el.getAttribute('contenteditable') === 'true')) {
        if (el.tagName === 'TEXTAREA') {
            el.value = arguments[0];
        } else {
            el.innerText = arguments[0];
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.focus();
        return true;
    }
    return false;
    """
    ok = driver.execute_script(js_code, prompt)
    if not ok:
        raise RuntimeError("Could not move focus into the chat composer.")

    # 4. Press Enter to actually submit
    ActionChains(driver).send_keys(Keys.ENTER).perform()

    # 5. Let the model respond
    time.sleep(wait_time)



def click_markdown_links(driver, link_texts: List[str], timeout: int = 60):
    """
    Click links in the last assistant message by visible text (e.g., 'blog_post.md').
    """
    for text in link_texts:
        try:
            elem = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, f"//a[normalize-space(text())='{text}']"))
            )
            elem.click()
            time.sleep(2)
        except Exception:
            # Sometimes links are buttons; try a contains() fallback
            try:
                elem = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//*[self::a or self::button][contains(., '{text}')]"))
                )
                elem.click()
                time.sleep(2)
            except Exception as e:
                raise RuntimeError(f"Could not click link/button with text '{text}'.") from e


# ────────────────────────────────────────────────────────────────────────────────
# Back-compat shim (optional)
# ────────────────────────────────────────────────────────────────────────────────

import glob
def move_latest_markdown(download_dir: str, target_path: str) -> str:
    """
    Find the newest .md in download_dir and move it to target_path.
    Returns the destination path.
    """
    download_dir = str(download_dir)
    candidates = sorted(
        glob.glob(os.path.join(download_dir, "*.md")),
        key=lambda p: os.path.getmtime(p),
        reverse=True
    )
    if not candidates:
        raise FileNotFoundError(f"No .md files found in {download_dir}")
    src = candidates[0]
    dest = str(Path(target_path))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    os.replace(src, dest)
    return dest