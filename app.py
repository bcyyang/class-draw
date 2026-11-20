# ... existing code ...
import base64
import streamlit as st
import streamlit.components.v1 as components
import qrcode

# ==========================================
# ... existing code ...
def generate_qr_base64(url_text):
    """產生學生掃碼用 QR Code 圖片（Base64 內嵌）"""
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def play_sound_effect(kind="fanfare", enabled=True):
    """透過瀏覽器 Web Audio API 合成跳號與中籤音效（免外部音檔）"""
    if not enabled:
        return
    uid = random.randint(100000, 999999)
    if kind == "rolling":
        js_code = f"""
        <script>
        (function() {{
            try {{
                const AudioCtx = window.parent.AudioContext || window.parent.webkitAudioContext || window.AudioContext || window.webkitAudioContext;
                const ctx = new AudioCtx();
                if (ctx.state === 'suspended') ctx.resume();
                for (let i = 0; i < 14; i++) {{
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(480 + (i % 5) * 95, ctx.currentTime + i * 0.085);
                    gain.gain.setValueAtTime(0.14, ctx.currentTime + i * 0.085);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.085 + 0.06);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(ctx.currentTime + i * 0.085);
                    osc.stop(ctx.currentTime + i * 0.085 + 0.065);
                }}
            }} catch (e) {{}}
        }})();
        // {uid}
        </script>
        """
    else:
        js_code = f"""
        <script>
        (function() {{
            try {{
                const AudioCtx = window.parent.AudioContext || window.parent.webkitAudioContext || window.AudioContext || window.webkitAudioContext;
                const ctx = new AudioCtx();
                if (ctx.state === 'suspended') ctx.resume();
                const notes = [523.25, 659.25, 783.99, 1046.50];
                notes.forEach((freq, idx) => {{
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.095);
                    gain.gain.setValueAtTime(0.22, ctx.currentTime + idx * 0.095);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.095 + 0.32);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(ctx.currentTime + idx * 0.095);
                    osc.stop(ctx.currentTime + idx * 0.095 + 0.34);
                }});
            }} catch (e) {{}}
        }})();
        // {uid}
        </script>
        """
    components.html(js_code, height=0, width=0)


# ==========================================
# ... existing code ...
if "draw_count" not in st.session_state:
    st.session_state.draw_count = 1

if "sound_enabled" not in st.session_state:
    st.session_state.sound_enabled = True

if "play_fanfare_once" not in st.session_state:
    st.session_state.play_fanfare_once = False

if "student_saved_num" not in st.session_state:
# ... existing code ...
    # --- 主畫面雙欄：左側抽籤舞台與候選名單（8份） / 右側抽籤設定與 QR Code（4份） ---
    left_col, right_col = st.columns([8, 4], gap="large")

    # 若剛完成抽籤，觸發一次勝利和弦音效
    if st.session_state.play_fanfare_once:
        play_sound_effect("fanfare", enabled=st.session_state.sound_enabled)
        st.session_state.play_fanfare_once = False

    # ---------------- 左側欄位 ----------------
# ... existing code ...
            st.session_state.draw_count = st.number_input(
                "本題抽取人數（位）",
                min_value=1,
                max_value=10,
                value=st.session_state.draw_count,
                step=1,
            )

            st.session_state.sound_enabled = st.toggle(
                "🔊 啟用抽籤跳號與中獎音效",
                value=st.session_state.sound_enabled,
            )

            if st.button("🎰 開始公平抽籤", type="primary", use_container_width=True):
                current_candidates = dict(state["candidates"])
                if not current_candidates:
                    st.warning("目前候選名單為空，請先等待學生舉手或點擊模擬加入！")
                else:
                    winners = pick_weighted_candidates(
                        current_candidates,
                        state["picked_history"],
                        st.session_state.draw_count,
                        weighted=(st.session_state.draw_mode == "weighted"),
                    )
                    pool_nums = list(current_candidates.keys())

                    # 啟動約 1.3 秒跳號滾動音效
                    play_sound_effect("rolling", enabled=st.session_state.sound_enabled)

                    # 播放約 1.3 秒跳號滾動動畫
                    for _ in range(15):
                        fake_sample = [random.choice(pool_nums) for _ in range(len(winners))]
                        spotlight_placeholder.markdown(
                            render_spotlight_html(fake_sample, rolling=True, total_pool=len(pool_nums)),
                            unsafe_allow_html=True,
                        )
                        time.sleep(0.085)

                    # 寫入最終中籤結果：從候選名單移除並累加發言次數
                    with state["lock"]:
                        for w in winners:
                            state["candidates"].pop(w, None)
                            state["picked_history"][w] = state["picked_history"].get(w, 0) + 1
                        state["last_winners"] = winners

                    st.session_state.play_fanfare_once = True
                    st.balloons()
                    st.rerun()
# ... existing code ...