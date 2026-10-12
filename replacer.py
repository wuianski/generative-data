"""Replace Instagram feed images and videos with #0F0 blocks.

Same Firefox profile, login, and scroll as scraper.py. A frame loop stays
installed because Instagram redraws the feed and clears one-time styles.
Post photos and videos become #0F0 rectangles. Circular photos — story
avatars, post avatars, and any other round image — become #0F0 circles.
Usernames and captions stay visible.

    ~/miniforge3/envs/scraper/bin/python replacer.py --scrolls 40
"""

import argparse
import time

from scraper import (
    MAX_SCROLLS,
    SCROLL_PAUSE,
    get_driver,
    keep_system_awake,
    login,
    wait_for_page,
)

GREEN = "#0F0"

# Re-applied every frame so a redraw cannot bring the picture back.
INSTALL_JS = """
const green = arguments[0];
if (window.__gmReplacerInstalled) return window.__gmReplacerCount || 0;
window.__gmReplacerInstalled = true;
window.__gmReplacerCount = 0;

const style = document.createElement('style');
style.id = 'gm-replacer-style';
style.textContent = `
  .gm-media { opacity: 0 !important; visibility: hidden !important; }
  .gm-frame { background-color: ${green} !important; background-image: none !important; }
  .gm-circle { border-radius: 50% !important; overflow: hidden !important; }
`;
(document.head || document.documentElement).appendChild(style);

function roundFrame(el) {
  const own = el.getBoundingClientRect();
  let node = el.parentElement;
  for (let i = 0; i < 6 && node && node !== document.body; i++) {
    const box = node.getBoundingClientRect();
    const radius = getComputedStyle(node).borderRadius || '';
    const square = box.width >= 16 && box.width <= 160
      && Math.abs(box.width - box.height) <= 12;
    const round = (radius.indexOf('%') !== -1 && parseFloat(radius) >= 40)
      || parseFloat(radius) >= box.width / 2 - 2;
    if (square && round) return node;
    node = node.parentElement;
  }
  if (own.width >= 16 && own.width <= 160 && el.parentElement) {
    const radius = getComputedStyle(el).borderRadius || '';
    const round = (radius.indexOf('%') !== -1 && parseFloat(radius) >= 40)
      || parseFloat(radius) >= own.width / 2 - 2;
    if (round) return el.parentElement;
  }
  return null;
}

function paint() {
  for (const el of document.querySelectorAll('img, video, canvas')) {
    const box = el.getBoundingClientRect();
    const w = box.width || 0;
    const h = box.height || 0;
    if (w < 16 || h < 16) continue;
    const inArticle = !!el.closest('article');
    const avatarCanvas = el.tagName === 'CANVAS' && w <= 140 && h <= 140
      && Math.abs(w - h) <= 24;
    const round = el.tagName !== 'VIDEO' && w <= 160 && h <= 160 ? roundFrame(el) : null;
    if (!inArticle && !round && !avatarCanvas) continue;

    const parent = round || el.parentElement;
    if (!parent) continue;
    const parentBox = parent.getBoundingClientRect();
    const slack = el.tagName === 'CANVAS' ? 24 : 12;
    const sameBox = Math.abs(parentBox.width - w) <= slack
      && Math.abs(parentBox.height - h) <= slack;
    const text = (parent.innerText || '').replace(/\\s+/g, '');
    const avatar = parentBox.width <= 120 && parentBox.height <= 140
      && Math.abs(parentBox.width - parentBox.height) <= 30;
    const tight = (sameBox || round || avatarCanvas)
      && !text
      && parentBox.width <= Math.max(w + 16, 80);

    el.classList.add('gm-media');
    el.style.setProperty('opacity', '0', 'important');
    el.style.setProperty('visibility', 'hidden', 'important');
    if (tight) {
      parent.classList.add('gm-frame');
      parent.style.setProperty('background-color', green, 'important');
      parent.style.setProperty('background-image', 'none', 'important');
      if (avatar) {
        parent.classList.add('gm-circle');
        parent.style.setProperty('border-radius', '50%', 'important');
        parent.style.setProperty('overflow', 'hidden', 'important');
      }
    }
    if (el.tagName === 'VIDEO' && !el.paused) {
      el.muted = true;
      el.pause();
    }
    if (el.dataset.gmSeen !== '1') {
      el.dataset.gmSeen = '1';
      window.__gmReplacerCount += 1;
    }
  }
  return window.__gmReplacerCount;
}

const loop = () => {
  paint();
  requestAnimationFrame(loop);
};
requestAnimationFrame(loop);
return paint();
"""


def replace(scrolls: int) -> float:
    started = time.perf_counter()
    keep_system_awake(True)
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

        total = int(driver.execute_script(INSTALL_JS, GREEN) or 0)
        print(f"Green blocks before scrolling: {total}")
        time.sleep(3)

        for i in range(scrolls):
            if not driver.window_handles:
                raise RuntimeError("Browser window was closed — aborting")
            driver.switch_to.window(driver.window_handles[0])
            driver.execute_script(
                "window.scrollBy(0, Math.round(window.innerHeight * 0.55));"
            )
            time.sleep(SCROLL_PAUSE)
            total = int(driver.execute_script("return window.__gmReplacerCount || 0") or 0)
            print(f"scroll {i + 1}/{scrolls}, green blocks {total}")

        elapsed = time.perf_counter() - started
        print(f"Done in {elapsed:.1f}s. {total} green blocks. Closing the browser.")
        return elapsed
    finally:
        driver.quit()
        keep_system_awake(False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Hide IG feed images and videos and paint #0F0 blocks"
    )
    parser.add_argument(
        "--scrolls",
        type=int,
        default=20,
        help=f"how many times to scroll the feed (max {MAX_SCROLLS})",
    )
    args = parser.parse_args()
    replace(max(1, min(args.scrolls, MAX_SCROLLS)))
