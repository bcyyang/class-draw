import io
import time
import random
import base64
import threading
import streamlit as st
import streamlit.components.v1 as components
import qrcode

# ==========================================
# 1. 頁面基本設定與全域視覺樣式 (CSS)
# ==========================================
st.set_page_config(
    page_title="課堂即時搶答抽籤系統",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans TC', sans-serif;
}

.block-container {
    padding-top: 2.6rem;
    padding-bottom: 1.5rem;
    padding-left: 1.8rem;
    padding-right: 1.8rem;
    max-width: 1440px;
}

/* 候選人卡片樣式（加大清晰版，向下自然延伸） */
.candidate-card {
    background: #f8fafc;
    border: 2px solid #e2e8f0;
    border-radius: 14px;
    padding: 12px 8px;
    text-align: center;
    margin-bottom: 10px;
    transition: transform 0.15s ease;
}
.candidate-card.weighted-top {
    border-color: #fbbf24;
    background: #fffbeb;
}
.candidate-num {
    font-size: 1.75rem;
    font-weight: 900;
    color: #0f172a;
    line-height: 1.2;
}
.badge-3x {
    display: inline-block;
    background: #fbbf24;
    color: #0f172a;
    font-size: 0.75rem;
    font-weight: 900;
    padding: 2px 10px;
    border-radius: 999px;
    margin-top: 5px;
}
.badge-1x {
    display: inline-block;
    background: #e2e8f0;
    color: #475569;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 999px;
    margin-top: 5px;
}

/* 聚光燈舞台（加大型主舞台，遠距離投影更清晰） */
.spotlight-box {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 55%, #0f172a 100%);
    border-radius: 24px;
    padding: 24px 26px;
    color: #ffffff;
    text-align: center;
    box-shadow: 0 12px 30px rgba(30, 27, 75, 0.25);
    margin-bottom: 14px;
}
.spotlight-inner {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 20px;
    padding: 28px 20px;
    min-height: 215px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}
.winner-pill {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 146px;
    padding: 16px 28px;
    margin: 8px;
    border-radius: 24px;
    background: linear-gradient(180deg, #fde047 0%, #facc15 100%);
    color: #0f172a;
    border: 3px solid #ffffff;
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.32);
}
.rolling-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 124px;
    height: 124px;
    margin: 8px;
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.18);
    border: 3px solid rgba(253, 224, 71, 0.8);
    color: #ffffff;
    font-size: 3.1rem;
    font-weight: 900;
}

/* 學生端卡片 */
.student-header {
    background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%);
    color: #ffffff;
    padding: 26px 20px;
    border-radius: 24px;
    text-align: center;
    margin-bottom: 18px;
    box-shadow: 0 10px 24px rgba(79, 70, 229, 0.22);
}
.status-open {
    display: inline-block;
    background: #34d399;
    color: #064e3b;
    font-weight: 800;
    font-size: 0.8rem;
    padding: 4px 14px;
    border-radius: 999px;
    margin-top: 8px;
}
.status-closed {
    display: inline-block;
    background: #fb7185;
    color: #ffffff;
    font-weight: 800;
    font-size: 0.8rem;
    padding: 4px 14px;
    border-radius: 999px;
    margin-top: 8px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ==========================================
# 2. 全班共用記憶體狀態 (@st.cache_resource)
# ==========================================
@st.cache_resource
def get_shared_classroom_state():
    return {
        "lock": threading.Lock(),
        "course_title": "課堂即時搶答抽籤",
        "round_id": 1,
        "is_open": True,
        "candidates": {},      # { "05": timestamp }
        "picked_history": {},  # { "05": count }
        "last_winners": [],    # ["05", "18"]
    }

state = get_shared_classroom_state()
DEFAULT_PIN = "1234"

# ==========================================
# 3. 個人連線裝置狀態 (st.session_state)
# ==========================================
query_mode = st.query_params.get("mode", "")
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "admin" if query_mode == "admin" else "student"
elif query_mode == "admin":
    st.session_state.view_mode = "admin"

if "admin_unlocked" not in st.session_state:
    st.session_state.admin_unlocked = False
if "draw_mode" not in st.session_state:
    st.session_state.draw_mode = "weighted"
if "draw_count" not in st.session_state:
    st.session_state.draw_count = 1
if "student_saved_num" not in st.session_state:
    st.session_state.student_saved_num = ""
if "submitted_round" not in st.session_state:
    st.session_state.submitted_round = 0
if "student_url_input" not in st.session_state:
    st.session_state.student_url_input = "https://bcyyang-class-draw.streamlit.app/"
if "sound_enabled" not in st.session_state:
    st.session_state.sound_enabled = True
if "play_fanfare_once" not in st.session_state:
    st.session_state.play_fanfare_once = False

# ==========================================
# 4. 核心工具函式（加權抽籤、QR Code、Web Audio 音效）
# ==========================================
def normalize_seat_num(raw_text: str) -> str:
    """標準化座號：若為 1~9 的單一數字（如 '5'），自動補零成為 '05'"""
    clean = raw_text.strip().upper()
    if clean.isdigit() and len(clean) == 1:
        return clean.zfill(2)
    return clean


def play_sound_effect(kind: str, enabled: bool = True):
    """透過 Web Audio API 在瀏覽器合成跳號滴答聲與中獎勝利和弦"""
    if not enabled:
        return
    uid = f"{kind}_{time.time()}"
    if kind == "rolling":
        js_code = f"""
        <script>
        // {uid}
        (function() {{
            try {{
                const AudioCtx = window.parent.AudioContext || window.parent.webkitAudioContext || window.AudioContext || window.webkitAudioContext;
                const ctx = new AudioCtx();
                if (ctx.state === 'suspended') ctx.resume();
                for (let i = 0; i < 15; i++) {{
                    const t = ctx.currentTime + i * 0.085;
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(480 + (i % 5) * 65, t);
                    gain.gain.setValueAtTime(0.14, t);
                    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.06);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(t);
                    osc.stop(t + 0.065);
                }}
            }} catch (e) {{}}
        }})();
        </script>
        """
    else:
        js_code = f"""
        <script>
        // {uid}
        (function() {{
            try {{
                const AudioCtx = window.parent.AudioContext || window.parent.webkitAudioContext || window.AudioContext || window.webkitAudioContext;
                const ctx = new AudioCtx();
                if (ctx.state === 'suspended') ctx.resume();
                const notes = [523.25, 659.25, 783.99, 1046.50];
                notes.forEach((freq, idx) => {{
                    const t = ctx.currentTime + idx * 0.095;
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(freq, t);
                    gain.gain.setValueAtTime(0.22, t);
                    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.32);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(t);
                    osc.stop(t + 0.34);
                }});
            }} catch (e) {{}}
        }})();
        </script>
        """
    components.html(js_code, height=0, width=0)


def pick_weighted_candidates(candidates_dict, history_dict, count, weighted=True):
    pool = list(candidates_dict.keys())
    selected = []
    pick_total = min(count, len(pool))

    for _ in range(pick_total):
        if weighted:
            weights = [3 if history_dict.get(num, 0) == 0 else 1 for num in pool]
        else:
            weights = [1 for _ in pool]

        chosen = random.choices(pool, weights=weights, k=1)[0]
        selected.append(chosen)
        pool.remove(chosen)

    return selected


def generate_qr_base64(url_text: str) -> str:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def render_spotlight_html(winners, rolling=False, total_pool=0):
    if rolling:
        pills = "".join(f'<div class="rolling-pill">{num}</div>' for num in winners)
        inner = (
            f'<div style="color:#fde047; font-size:0.95rem; font-weight:800; letter-spacing:0.06em; margin-bottom:12px;">'
            f'🎰 正在從 {total_pool} 位舉手同學中抽出 {len(winners)} 位...</div>'
            f'<div style="display:flex; flex-wrap:wrap; justify-content:center; align-items:center;">{pills}</div>'
        )
    elif winners:
        pills = "".join(
            f'<div class="winner-pill">'
            f'<span style="background:#78350f; color:#fef08a; font-size:0.82rem; font-weight:900; padding:2px 12px; border-radius:999px; letter-spacing:0.06em; margin-bottom:4px;">第 {idx + 1} 位</span>'
            f'<span style="font-size:3.6rem; font-weight:900; line-height:1.05; margin-top:2px;">{num}</span>'
            f'</div>'
            for idx, num in enumerate(winners)
        )
        inner = (
            f'<div style="color:#fde047; font-size:0.98rem; font-weight:800; letter-spacing:0.06em; margin-bottom:10px;">'
            f'🎉 恭喜以下 {len(winners)} 位同學獲得發言機會！</div>'
            f'<div style="display:flex; flex-wrap:wrap; justify-content:center; align-items:center;">{pills}</div>'
        )
    else:
        inner = (
            '<div style="color:#e0e7ff; font-size:1.18rem; font-weight:700;">'
            '等待同學舉手加入名單後，點擊右側「開始公平抽籤」</div>'
            '<div style="color:#a5b4fc; font-size:0.86rem; margin-top:6px;">'
            '抽中後將自動從本題候選名單移除，並更新加權紀錄</div>'
        )
    return (
        '<div class="spotlight-box">'
        '<div style="text-align:left; font-size:1.2rem; font-weight:900; margin-bottom:12px;">🎯 本題中籤發言同學</div>'
        f'<div class="spotlight-inner">{inner}</div>'
        '</div>'
    )


# ==========================================
# 5. 頂部精簡視角切換列（縮小高度不佔版面）
# ==========================================
nav_col1, nav_col2, nav_col3 = st.columns([8.2, 0.9, 0.9])
with nav_col1:
    st.markdown(
        '<div style="font-size:0.78rem; color:#64748b; padding-top:4px;">💡 同網址雙模式：預設為學生端；網址加 <code>?mode=admin</code> 即為老師端</div>',
        unsafe_allow_html=True,
    )
with nav_col2:
    if st.button(
        "📱 學生端",
        use_container_width=True,
        type="primary" if st.session_state.view_mode == "student" else "secondary",
    ):
        st.session_state.view_mode = "student"
        st.query_params.clear()
        st.rerun()
with nav_col3:
    if st.button(
        "🖥️ 老師端",
        use_container_width=True,
        type="primary" if st.session_state.view_mode == "admin" else "secondary",
    ):
        st.session_state.view_mode = "admin"
        st.query_params["mode"] = "admin"
        st.rerun()

# ==========================================
# 6. 老師大螢幕端 (ADMIN VIEW)
# ==========================================
if st.session_state.view_mode == "admin":

    # --- PIN 碼安全鎖 ---
    if not st.session_state.admin_unlocked:
        _, lock_col, _ = st.columns([1, 1.4, 1])
        with lock_col:
            st.markdown("### 🔒 老師主控台解鎖")
            st.caption("預設 PIN 碼為 `1234`（解鎖後本機連線期間將自動記住）")
            pin_val = st.text_input("請輸入 4 碼 PIN 碼", type="password", max_chars=4)
            if st.button("確認解鎖", type="primary", use_container_width=True):
                if pin_val.strip() == DEFAULT_PIN:
                    st.session_state.admin_unlocked = True
                    st.rerun()
                else:
                    st.error("PIN 碼錯誤，請重新輸入！")
        st.stop()

    # --- 頂部課程標題與開題控制列（加寬題次與重置題次按鈕，確保清晰可見） ---
    top_c1, top_c2, top_c2_reset, top_c3, top_c4 = st.columns([3.3, 1.4, 1.3, 2.0, 2.0])
    with top_c1:
        new_title = st.text_input(
            "課程名稱",
            value=state["course_title"],
            label_visibility="collapsed",
        )
        if new_title.strip() and new_title != state["course_title"]:
            with state["lock"]:
                state["course_title"] = new_title.strip()

    with top_c2:
        st.markdown(
            f'<div style="background:#eef2ff; border:1px solid #c7d2fe; border-radius:10px; padding:6px 8px; text-align:center; font-weight:900; color:#1e1b4b; font-size:1.05rem;">第 {state["round_id"]} 題</div>',
            unsafe_allow_html=True,
        )

    with top_c2_reset:
        if st.button("🔄 題次歸 1", use_container_width=True, help="將題次重置回到第 1 題，並清空當前名單"):
            with state["lock"]:
                state["round_id"] = 1
                state["is_open"] = True
                state["candidates"] = {}
                state["last_winners"] = []
            st.toast("↩️ 已將題次重置為第 1 題！")
            st.rerun()

    with top_c3:
        if state["is_open"]:
            if st.button("🟢 報名開放中（點擊截止）", use_container_width=True):
                with state["lock"]:
                    state["is_open"] = False
                st.rerun()
        else:
            if st.button("🔴 已截止報名（點擊重開）", use_container_width=True):
                with state["lock"]:
                    state["is_open"] = True
                st.rerun()

    with top_c4:
        if st.button("🔄 開啟新一題 / 清空名單", type="primary", use_container_width=True):
            with state["lock"]:
                state["round_id"] += 1
                state["is_open"] = True
                state["candidates"] = {}
                state["last_winners"] = []
            st.toast(f"✨ 已開啟第 {state['round_id']} 題，全班手機已自動解鎖！")
            st.rerun()

    # 若剛完成抽籤，觸發一次勝利和弦音效
    if st.session_state.play_fanfare_once:
        play_sound_effect("fanfare", enabled=st.session_state.sound_enabled)
        st.session_state.play_fanfare_once = False

    # --- 主內容經典雙欄網格：左側 8 欄（聚光燈 + 候選名單）/ 右側 4 欄（抽籤規則 + 已發言紀錄 + QR Code） ---
    left_col, right_col = st.columns([8, 4], gap="large")

    # ---------------- 左側 8 欄：抽籤結果聚光燈 + 即時候選名單 ----------------
    with left_col:
        spotlight_placeholder = st.empty()
        spotlight_placeholder.markdown(
            render_spotlight_html(state["last_winners"], rolling=False),
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            @st.fragment(run_every=2)
            def live_candidate_board():
                candidates = state["candidates"]
                history = state["picked_history"]
                sorted_nums = sorted(candidates.keys(), key=lambda k: candidates[k])

                header_c1, header_c2, header_c3, header_c4 = st.columns([3.5, 2.2, 2.0, 1.3])
                with header_c1:
                    st.markdown(f"#### 🙋 本題舉手候選名單（{len(sorted_nums)} 人）")
                with header_c2:
                    if st.button("✨ 模擬 8 位學生加入", use_container_width=True):
                        sample_pool = ["01", "03", "07", "11", "14", "18", "22", "25", "29", "33", "36", "40"]
                        available = [n for n in sample_pool if n not in state["candidates"]]
                        to_add = random.sample(available, min(8, len(available)))
                        with state["lock"]:
                            now_ts = time.time()
                            for idx, num in enumerate(to_add):
                                state["candidates"][num] = now_ts + idx * 0.01
                        st.rerun()
                with header_c3:
                    manual_num = st.text_input(
                        "手動座號",
                        placeholder="手動座號",
                        label_visibility="collapsed",
                        key="manual_add_box",
                    )
                with header_c4:
                    if st.button("➕ 加入", use_container_width=True):
                        clean = normalize_seat_num(manual_num)
                        if clean:
                            with state["lock"]:
                                state["candidates"][clean] = time.time()
                            st.rerun()

                if not sorted_nums:
                    st.markdown(
                        '<div style="border:2px dashed #cbd5e1; border-radius:16px; padding:42px 20px; text-align:center; background:#f8fafc; color:#64748b; margin-top:6px;">'
                        '<div style="font-weight:800; font-size:1.05rem;">目前還沒有同學舉手加入本題名單</div>'
                        '<div style="font-size:0.86rem; margin-top:6px;">請學生掃描右側 QR Code 輸入座號，或點擊「模擬 8 位學生加入」測試</div>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    cols = st.columns(4)
                    for idx, num in enumerate(sorted_nums):
                        picked_times = history.get(num, 0)
                        is_top = st.session_state.draw_mode == "weighted" and picked_times == 0
                        card_cls = "candidate-card weighted-top" if is_top else "candidate-card"
                        if st.session_state.draw_mode == "weighted":
                            badge_html = (
                                '<span class="badge-3x">3x 優先</span>'
                                if picked_times == 0
                                else f'<span class="badge-1x">1x (已答{picked_times}次)</span>'
                            )
                        else:
                            badge_html = (
                                f'<span class="badge-1x">已答{picked_times}次</span>'
                                if picked_times > 0
                                else '<span class="badge-1x" style="background:#d1fae5;color:#065f46;">尚未發言</span>'
                            )

                        with cols[idx % 4]:
                            st.markdown(
                                f'<div class="{card_cls}"><div class="candidate-num">{num}</div>{badge_html}</div>',
                                unsafe_allow_html=True,
                            )

            live_candidate_board()

    # ---------------- 右側 4 欄：抽籤規則 + 已發言紀錄 + QR Code ----------------
    with right_col:
        # 1. 抽籤規則與啟動卡片
        with st.container(border=True):
            st.markdown("#### 🎲 抽籤規則與啟動")
            mode_choice = st.radio(
                "抽籤演算法模式",
                options=["weighted", "equal"],
                format_func=lambda x: (
                    "未曾抽中者優先加權（3x 優先，推薦）" if x == "weighted" else "純粹均等亂數（所有人 1x）"
                ),
                index=0 if st.session_state.draw_mode == "weighted" else 1,
            )
            if mode_choice != st.session_state.draw_mode:
                st.session_state.draw_mode = mode_choice
                st.rerun()

            st.session_state.draw_count = st.number_input(
                "本題抽取人數（位）",
                min_value=1,
                max_value=50,
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

                    play_sound_effect("rolling", enabled=st.session_state.sound_enabled)

                    for _ in range(15):
                        fake_sample = [random.choice(pool_nums) for _ in range(len(winners))]
                        spotlight_placeholder.markdown(
                            render_spotlight_html(fake_sample, rolling=True, total_pool=len(pool_nums)),
                            unsafe_allow_html=True,
                        )
                        time.sleep(0.085)

                    with state["lock"]:
                        for w in winners:
                            state["candidates"].pop(w, None)
                            state["picked_history"][w] = state["picked_history"].get(w, 0) + 1
                        state["last_winners"] = winners

                    st.session_state.play_fanfare_once = True
                    st.rerun()

        # 2. 本堂課已發言紀錄卡片（補回標題與一鍵重置紀錄按鈕）
        with st.container(border=True):
            hist_h1, hist_h2 = st.columns([2.6, 1.4])
            with hist_h1:
                st.markdown("#### 📊 本堂課已發言紀錄")
            with hist_h2:
                if st.button("🗑️ 重置紀錄", use_container_width=True, help="清空所有已發言紀錄，所有人恢復 3x 優先權重"):
                    with state["lock"]:
                        state["picked_history"] = {}
                    st.toast("已清空本堂課已發言紀錄，所有人恢復 3x 優先加權！")
                    st.rerun()

            st.caption("作為「未曾抽中者 3x 加權」的依據；下課或換班時可點右上角重置。")

            if not state["picked_history"]:
                st.markdown(
                    '<div style="padding:14px 12px; border-radius:12px; background:#f8fafc; border:1px dashed #cbd5e1; color:#94a3b8; font-size:0.9rem; text-align:center;">尚未抽出任何同學</div>',
                    unsafe_allow_html=True,
                )
            else:
                sorted_hist = sorted(state["picked_history"].items(), key=lambda x: -x[1])
                badges_html = "".join(
                    f'<div style="display:inline-flex; align-items:center; gap:8px; background:#f1f5f9; border:2px solid #cbd5e1; border-radius:14px; padding:8px 14px; margin:4px 6px 4px 0;">'
                    f'<span style="font-size:1.35rem; font-weight:900; color:#0f172a;">{num}</span>'
                    f'<span style="background:#e0e7ff; color:#3730a3; font-size:0.85rem; font-weight:800; padding:3px 9px; border-radius:999px;">{cnt}次</span>'
                    f'</div>'
                    for num, cnt in sorted_hist
                )
                st.markdown(
                    f'<div style="display:flex; flex-wrap:wrap; align-items:center; padding-top:4px;">{badges_html}</div>',
                    unsafe_allow_html=True,
                )

        # 3. 學生掃碼 QR Code 卡片（移至最下方）
        with st.container(border=True):
            st.markdown("#### 📱 學生手機掃碼加入")
            share_url = st.text_input(
                "學生端網址（可貼上你的 Streamlit 公開網址自動更新二維碼）",
                value=st.session_state.student_url_input,
            )
            st.session_state.student_url_input = share_url
            if share_url.strip():
                qr_b64 = generate_qr_base64(share_url.strip())
                st.markdown(
                    f'<div style="text-align:center; padding:4px 0;"><img src="data:image/png;base64,{qr_b64}" width="150" style="border-radius:12px; border:1px solid #e2e8f0; padding:6px; background:#fff;"/></div>',
                    unsafe_allow_html=True,
                )


# ==========================================
# 7. 學生手機端 (STUDENT VIEW)
# ==========================================
else:
    _, stu_col, _ = st.columns([1, 1.4, 1])
    with stu_col:

        @st.fragment(run_every=2)
        def student_live_panel():
            current_round = state["round_id"]
            is_open = state["is_open"]
            already_submitted = st.session_state.submitted_round == current_round

            status_badge = (
                '<div class="status-open">● 開放舉手搶答中</div>'
                if is_open
                else '<div class="status-closed">● 本題已截止報名</div>'
            )

            st.markdown(
                f"""
                <div class="student-header">
                    <div style="font-size:0.82rem; font-weight:700; opacity:0.9;">{state['course_title']}</div>
                    <div style="font-size:2.1rem; font-weight:900; margin-top:4px;">第 {current_round} 題</div>
                    {status_badge}
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.container(border=True):
                last_winners = state.get("last_winners", [])
                saved_num = st.session_state.student_saved_num

                if already_submitted and saved_num and saved_num in last_winners:
                    order_num = last_winners.index(saved_num) + 1
                    st.markdown(
                        f"""
                        <div style="background:linear-gradient(135deg, #fde047 0%, #facc15 100%); border:3px solid #eab308; border-radius:20px; padding:24px 16px; text-align:center; color:#0f172a; box-shadow:0 10px 25px rgba(250,204,21,0.35);">
                            <div style="font-size:2.6rem; line-height:1;">🎉</div>
                            <div style="display:inline-block; background:#78350f; color:#fef08a; font-size:0.95rem; font-weight:900; padding:4px 16px; border-radius:999px; margin-top:8px;">
                                第 {order_num} 位發言
                            </div>
                            <div style="font-size:1.45rem; font-weight:900; margin-top:10px;">恭喜 {saved_num} 號中籤！</div>
                            <div style="font-size:0.9rem; font-weight:700; color:#422006; margin-top:6px;">
                                請準備回答問題 🎤
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                elif already_submitted:
                    st.success(f"✅ 已加入第 **{current_round}** 題候選名單！")
                    st.markdown(f"你的登記座號：**`{saved_num}`**")
                    if last_winners:
                        st.warning(f"📢 本輪已抽出座號：**{'、'.join(last_winners)}**（若老師繼續加抽仍有機會喔！）")
                    else:
                        st.info("👀 請抬頭看教室大螢幕等待老師抽籤！當老師開啟**下一題**時，此畫面會自動解鎖。")
                elif not is_open:
                    st.warning("⏸️ 本題已截止舉手報名，老師正在進行抽籤或討論中，請等待下一題！")
                else:
                    num_input = st.text_input(
                        "請輸入你的座號",
                        value=st.session_state.student_saved_num,
                        max_chars=10,
                        placeholder="例如：05 或 28",
                    )
                    st.caption("系統會自動記住你的號碼，下一題免重新輸入")
                    if st.button("🙋 舉手搶答！送出號碼", type="primary", use_container_width=True):
                        clean_num = normalize_seat_num(num_input)
                        if not clean_num:
                            st.error("請先輸入你的座號！")
                        elif not state["is_open"]:
                            st.warning("本題剛剛已截止報名囉！")
                        else:
                            with state["lock"]:
                                state["candidates"][clean_num] = time.time()
                            st.session_state.student_saved_num = clean_num
                            st.session_state.submitted_round = current_round
                            st.rerun()

        student_live_panel()