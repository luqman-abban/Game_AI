import streamlit as st
import time, sys, subprocess
from io import BytesIO
from pathlib import Path
from playwright.sync_api import sync_playwright

st.set_page_config(page_title="Online Game Auto-Player (Streamlit)", layout="wide")
st.title("Online Game Auto-Player (Streamlit)")
st.caption("Plays an online game in a headless Chromium via Playwright and streams frames.")

# ---------- Helpers ----------
MOVE_ORDERS = {
    "Up/Left Bias": ["ArrowUp", "ArrowLeft", "ArrowRight", "ArrowDown"],
    "Left/Down Bias": ["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp"],
    "Clockwise": ["ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft"],
}

def ensure_playwright():
    # Install Chromium once per session
    if not st.session_state.get("pw_installed", False):
        st.info("Installing Playwright Chromium… (first run only)")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        st.session_state["pw_installed"] = True

def get_score(page):
    try:
        txt = page.locator(".score-container").inner_text().strip()
        return int(txt.split()[0].replace(",", ""))
    except Exception:
        return 0

def is_game_over(page):
    return page.locator(".game-message.game-over, .game-over").count() > 0

def board_signature(page):
    # A quick DOM signature so we can detect whether a move changed the board
    classes = page.locator(".tile").evaluate_all("els => els.map(e => e.className)")
    return "|".join(sorted(classes)) if classes else ""

def autoplay_stream(url: str, moves: int, fps: int, strategy: str):
    ensure_playwright()
    move_order = MOVE_ORDERS[strategy].copy()
    frame_delay = max(0.07, 1.0 / max(1, fps))  # seconds

    placeholder_img = st.empty()
    logs_box = st.empty()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = browser.new_page(viewport={"width": 850, "height": 1000})
        page.goto(url, wait_until="load", timeout=60_000)
        page.mouse.click(50, 50)  # focus the game area

        logs = [f"Loaded: {url}"]
        last_sig = board_signature(page)
        invalid = 0
        last_frame = 0.0

        # initial frame
        placeholder_img.image(page.screenshot(full_page=True), caption="Live view")
        logs_box.code("\n".join(logs), language="text")

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

            last_sig = sig
            score = get_score(page)
            logs.append(f"Move {i+1:03d} | Score {score}")
            if len(logs) > 80:
                logs = logs[-80:]

            now = time.time()
            if now - last_frame >= frame_delay:
                placeholder_img.image(page.screenshot(full_page=True), caption=f"Score {score}")
                logs_box.code("\n".join(logs), language="text")
                last_frame = now

            if is_game_over(page):
                logs.append("Game Over detected. Stopping.")
                placeholder_img.image(page.screenshot(full_page=True), caption=f"Final (Score {score})")
                logs_box.code("\n".join(logs), language="text")
                break

            if invalid >= 3:
                # rotate to escape dead patterns
                first = move_order.pop(0)
                move_order.append(first)
                logs.append(f"Rotated move order -> {move_order}")
                invalid = 0

        browser.close()

# ---------- UI ----------
with st.sidebar:
    url = st.text_input("Game URL", "https://play2048.co")
    moves = st.slider("Max moves", 50, 1200, 300, 10)
    fps = st.slider("Stream FPS", 1, 12, 5, 1)
    strategy = st.selectbox("Move strategy", list(MOVE_ORDERS.keys()))
    go = st.button("Start")

col1, col2 = st.columns([2, 1], gap="large")
with col1:
    st.markdown("#### Live View")
with col2:
    st.markdown("#### Logs")

if go:
    autoplay_stream(url, moves, fps, strategy)
else:
    st.info("Set the options in the sidebar and click **Start**.")
