import streamlit as st
import time
from playwright.sync_api import sync_playwright, Error as PWError

st.set_page_config(page_title="Online Game Auto-Player", layout="wide")
st.title("🎮 Online Game Auto-Player")
st.caption("Plays online games in headless Chromium using Playwright")

DEFAULT_URL = "https://play2048.co"
MOVE_ORDERS = {
    "Up/Left Bias": ["ArrowUp", "ArrowLeft", "ArrowRight", "ArrowDown"],
    "Left/Down Bias": ["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp"],
    "Clockwise": ["ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft"],
}

def get_score(page):
    try:
        txt = page.locator(".score-container").inner_text(timeout=1000).strip()
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
    img_ph = st.empty()
    logs_ph = st.empty()
    logs = [f"Loading: {url}"]
    logs_ph.code("\n".join(logs), language="text")
    
    frame_delay = max(0.1, 1.0 / max(1, fps))
    move_order = MOVE_ORDERS[strategy].copy()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = browser.new_context(viewport={"width": 500, "height": 700})
            page = context.new_page()
            
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1000)  # Initial load
            
            logs.append("Page loaded. Starting game...")
            logs_ph.code("\n".join(logs), language="text")
            img_ph.image(page.screenshot(), caption="Initial view")

            last_sig = board_signature(page)
            invalid_count = 0
            last_update = time.time()

            for i in range(moves):
                page.keyboard.press(move_order[i % 4])
                page.wait_for_timeout(100)  # Game response time
                
                # Check if board changed
                new_sig = board_signature(page)
                if new_sig == last_sig:
                    invalid_count += 1
                else:
                    invalid_count = 0
                    last_sig = new_sig
                
                # Rotate strategy if stuck
                if invalid_count >= 3:
                    move_order.append(move_order.pop(0))
                    logs.append(f"♻️ Strategy rotated: {move_order}")
                    invalid_count = 0
                
                # Update UI periodically
                current_time = time.time()
                if current_time - last_update >= frame_delay:
                    score = get_score(page)
                    logs.append(f"Move {i+1}/{moves} | Score: {score}")
                    if len(logs) > 15:
                        logs = logs[-15:]
                    
                    img_ph.image(page.screenshot(), caption=f"Score: {score}")
                    logs_ph.code("\n".join(logs), language="text")
                    last_update = current_time
                
                # Check game over
                if is_game_over(page):
                    score = get_score(page)
                    logs.append(f"🏁 Game Over! Final score: {score}")
                    img_ph.image(page.screenshot(), caption=f"Final Score: {score}")
                    logs_ph.code("\n".join(logs), language="text")
                    break

            # Cleanup
            context.close()
            browser.close()

    except PWError as e:
        st.error("Browser error occurred")
        st.code(str(e), language="text")
    except Exception as e:
        st.error("Unexpected error")
        st.code(str(e), language="text")

# UI Layout
with st.sidebar:
    st.header("Settings")
    url = st.text_input("Game URL", DEFAULT_URL)
    moves = st.slider("Max moves", 50, 500, 150)
    fps = st.slider("Update Frequency (FPS)", 1, 10, 3)
    strategy = st.selectbox("Move Strategy", list(MOVE_ORDERS.keys()))
    
    if st.button("▶️ Start Game", type="primary"):
        autoplay(url, moves, fps, strategy)

st.info("Configure settings in the sidebar and press 'Start Game'")
