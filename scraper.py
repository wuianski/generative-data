"""Scrape images from the Instagram home feed.

Downloads up to LIMIT unique post images from the logged-in home feed into
data/YYYY-MM-DD/images/NNN.jpg. Uses a persistent Firefox profile so the login
session survives between runs (log in manually once, then cookies are reused).

Run with the `scraper` conda env:
    ~/miniforge3/envs/scraper/bin/python scraper.py --limit 100
"""

import argparse
import hashlib
import io
import json
import os
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

REPO_ROOT = Path(__file__).resolve().parent
DATA_ROOT = REPO_ROOT / "data"
PROFILE_DIR = REPO_ROOT / "firefox_profile"
SEEN_HASHES_FILE = REPO_ROOT / "seen_hashes.json"

MIN_DIMENSION = 300      # skip avatars / icons
SCROLL_PAUSE = 4         # seconds between scrolls
MAX_SCROLLS = 120        # safety cap so the loop always terminates

load_dotenv(REPO_ROOT / ".env")
USERNAME = os.getenv("INSTAGRAM_USERNAME")
PASSWORD = os.getenv("INSTAGRAM_PASSWORD")


def load_seen_hashes() -> set:
    if SEEN_HASHES_FILE.exists():
        return set(json.loads(SEEN_HASHES_FILE.read_text()))
    return set()


def save_seen_hashes(hashes: set) -> None:
    SEEN_HASHES_FILE.write_text(json.dumps(sorted(hashes)))


def get_driver() -> webdriver.Firefox:
    PROFILE_DIR.mkdir(exist_ok=True)
    options = Options()
    options.add_argument("--width=800")
    options.add_argument("--height=1440")
    # Persistent profile keeps the IG session between runs.
    options.add_argument("-profile")
    options.add_argument(str(PROFILE_DIR))
    # Don't show the "Restore session?" page if a previous run crashed/was killed.
    options.set_preference("browser.sessionstore.resume_from_crash", False)
    driver = webdriver.Firefox(options=options)
    driver.set_window_position(0, 0)
    return driver


def is_login_page(driver) -> bool:
    return len(driver.find_elements(By.NAME, "username")) > 0


def login(driver) -> None:
    if not USERNAME or not PASSWORD:
        raise ValueError("INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD must be set in .env")
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    print("Submitted login form")
    time.sleep(8)
    dismiss_dialogs(driver)


def dismiss_dialogs(driver) -> None:
    """Dismiss cookie-consent / 'Save your login info?' / notification dialogs."""
    labels = ("Allow all cookies", "Decline optional cookies", "Not now", "Not Now")
    for label in labels:
        for el in driver.find_elements(By.XPATH, f"//*[text()='{label}']"):
            try:
                el.click()
                print(f"Dismissed dialog: {label}")
                time.sleep(2)
                return
            except Exception:
                pass


def wait_for_page(driver, timeout: int = 30) -> str:
    """Wait until either the login form or the feed is present."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        dismiss_dialogs(driver)
        if is_login_page(driver):
            return "login"
        if driver.find_elements(By.CSS_SELECTOR, "article"):
            return "feed"
        time.sleep(2)
    return "unknown"


def best_src(img_element) -> str:
    """Pick the largest candidate URL from srcset, falling back to src."""
    srcset = img_element.get_attribute("srcset")
    if srcset:
        best_url, best_w = None, 0
        for candidate in srcset.split(","):
            parts = candidate.strip().split(" ")
            if len(parts) == 2 and parts[1].endswith("w"):
                try:
                    w = int(parts[1][:-1])
                except ValueError:
                    continue
                if w > best_w:
                    best_url, best_w = parts[0], w
        if best_url:
            return best_url
    return img_element.get_attribute("src")


def scrape(limit: int, run_date: str) -> Path:
    out_dir = DATA_ROOT / run_date / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    seen_hashes = load_seen_hashes()
    seen_urls = set()
    count = len(list(out_dir.glob("*.jpg")))  # resume if partially done today

    driver = get_driver()
    try:
        driver.get("https://www.instagram.com")
        time.sleep(6)
        print(f"Loaded: {driver.current_url} | title: {driver.title!r}")

        state = wait_for_page(driver)
        print(f"Page state: {state}")
        if state == "login":
            print("Not logged in, logging in...")
            login(driver)
            state = wait_for_page(driver)
            print(f"Page state after login: {state}")
        if state == "unknown":
            print("WARNING: neither login form nor feed detected; continuing anyway")

        scrolls = 0
        while count < limit and scrolls < MAX_SCROLLS:
            handles = driver.window_handles
            if not handles:
                raise RuntimeError("Browser window was closed — aborting")
            driver.switch_to.window(handles[0])

            print(f"scroll {scrolls + 1}/{MAX_SCROLLS}, images {count}/{limit}")
            for img in driver.find_elements(By.CSS_SELECTOR, "article img"):
                if count >= limit:
                    break
                try:
                    url = best_src(img)
                except Exception:
                    continue
                if not url or not url.startswith("http") or url in seen_urls:
                    continue
                seen_urls.add(url)

                try:
                    data = requests.get(url, timeout=15).content
                except requests.RequestException:
                    continue

                digest = hashlib.md5(data).hexdigest()
                if digest in seen_hashes:
                    continue

                try:
                    image = Image.open(io.BytesIO(data))
                except Exception:
                    continue
                if min(image.size) < MIN_DIMENSION:
                    continue  # avatar / icon / thumbnail

                count += 1
                seen_hashes.add(digest)
                filename = out_dir / f"{count:03d}.jpg"
                image.convert("RGB").save(filename, "JPEG", quality=92)
                print(f"[{count}/{limit}] saved {filename.name} ({image.size[0]}x{image.size[1]})")

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            scrolls += 1
            time.sleep(SCROLL_PAUSE)

        save_seen_hashes(seen_hashes)
        print(f"Done: {count} images in {out_dir}")
        return out_dir
    finally:
        driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape images from the IG home feed")
    parser.add_argument("--limit", type=int, default=100, help="number of images to download")
    parser.add_argument("--date", default=date.today().isoformat(), help="folder date (YYYY-MM-DD)")
    args = parser.parse_args()
    scrape(args.limit, args.date)
