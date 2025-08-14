import streamlit as st
import time, sys, subprocess, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright, Error as PWError

st.set_page_config(page_title="Online Game Auto-Player (Streamlit)", layout="wide")
st.title("Online Game Auto-Player (Streamlit)")
st.caption("Loads an online game in a headless Chromium via Playwright and streams frames.")

MOVE_ORDERS = {
    "Up/Left Bias": ["ArrowUp", "ArrowLeft", "ArrowRight", "ArrowDown"],
    "Left/Down Bias": ["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp"],
    "Clockwise": ["ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft"],
}
DEFAULT_URL = "https://play2048.co"

def ensure_pw_browsers():
    if not st.session_state.get("pw_installed"):
        st.info("Installing Playwright Chromium (first run only)...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        st.session_state["pw_installed"] = True

def get_score(page):
    try:
        txt = page.locator(".score-container").inner_text().strip()
        return int(txt.split()[0].replace(",", ""))
    except Exception:
        return 0

def is_game_over(page):
    try:
        return page.locator(".game-message.game-over, .game-over").count() > 0
    except Exception:
        return False

def board_signature(page):
    try:
        classes = page.locator(".tile").evaluate_all("els => els.map(e => e.className)")
        return "|".join(sorted(classes)) if classes else ""
    except Exception:
        return ""

def autoplay(url: str, moves: int, fps: int, strategy: str):
    # Install Chromium if needed
    ensure_pw_browsers()

    move_order = MOVE_ORDERS[strategy].copy()
    frame_delay = max(0.07, 1.0 / max(1, fps))

    img_ph = st.empty()
    logs_ph = st.empty()
    logs = [f"Loaded URL: {url}"]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            page = browser.new_page(viewport={"width": 850, "height": 1000})
            page.goto(url, wait_until="load", timeout=60_000)
            page.mouse.click(50, 50)

            img_ph.image(page.screenshot(full_page=True), caption="Live view")
            logs_ph.code("\n".join(logs), language="text")

            last_sig = board_signature(page)
            invalid = 0
            last_frame = 0.0

            for i in range(moves):
                page.keyboard.press(move_order[i % 4])
                page.wait_for_timeout(70)

                sig = board_signature(page)
                if sig == last_sig:
                    changed = False
                    for alt in move_order[1:]:
                        page.keyboard.press(alt)
                        page.wait_for_timeout(50)
                        new_sig = board_signature(page)
                        if new_sig != sig:
                            sig = new_sig
                            changed = True
                            break
                    if not changed:
                        invalid += 1
                else:
                    invalid = 0

                score = get_score(page)
                logs.append(f"Move {i+1:03d} | Score {score}")
                if len(logs) > 80:
                    logs = logs[-80:]

                now = time.time()
                if now - last_frame >= frame_delay:
                    img_ph.image(page.screenshot(full_page=True), caption=f"Score {score}")
                    logs_ph.code("\n".join(logs), language="text")
                    last_frame = now

                if is_game_over(page):
                    logs.append("Game Over detected. Stopping.")
                    img_ph.image(page.screenshot(full_page=True), caption=f"Final (Score {score})")
                    logs_ph.code("\n".join(logs), language="text")
                    break

                if invalid >= 3:
                    first = move_order.pop(0)
                    move_order.append(first)
                    logs.append(f"Rotated move order -> {move_order}")
                    invalid = 0

            browser.close()

    except subprocess.CalledProcessError as e:
        st.error("Chromium installer failed (playwright install chromium).")
        st.code(str(e), language="text")
    except PWError as e:
        st.error("Playwright error while launching or controlling Chromium.")
        st.code(str(e), language="text")
    except Exception:
        st.error("Unexpected error.")
        st.code(traceback.format_exc(), language="text")

# ---- UI ----
with st.sidebar:
    url = st.text_input("Game URL", DEFAULT_URL)
    moves = st.slider("Max moves", 50, 1200, 300, 10)
    fps = st.slider("Stream FPS", 1, 12, 5, 1)
    strategy = st.selectbox("Move strategy", list(MOVE_ORDERS.keys()))
    go = st.button("Start")

st.markdown("#### Live View")
img_area = st.empty()
st.markdown("#### Logs")
logs_area = st.empty()

if go:
    autoplay(url, moves, fps, strategy)
else:
    st.info("Set the options in the sidebar and click **Start**.")
