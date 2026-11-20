import time
import random
import threading
import io
import base64
import streamlit as st
import qrcode

# ==========================================
# 1. 頁面基本設定與自訂高質感 CSS（還原原版視覺風格）
# ==========================================
st.set_page_config(
    page_title="課堂即時搶答抽籤系統",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
    }

    /* 隱藏 Streamlit 預設右上角選單與頁尾，讓大螢幕投影更乾淨 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        max-width: 1280px;
    }

    /* 抽籤聚光燈深藍漸層舞台 */
    .spotlight-stage {
        background: linear-gradient(135deg, #312e81 0%, #3730a3 50%, #0f172a 100%);
        border-radius: 24px;
        padding: 28px;
        color: white;
        box-shadow: 0 20px 25px -5px rgba(49, 46, 129, 0.25);
        margin-bottom: 20px;
        text-align: center;
    }

    .spotlight-inner {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 18px;
        padding: 24px;
        min-height: 150px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    /* 中籤號碼金色大卡片 */
    .winner-card {
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: linear-gradient(180deg, #fde047 0%, #facc15 100%);
        color: #0f172a;
        border: 3px solid #ffffff;
        border-radius: 22px;
        padding: 14px 28px;
        margin: 8px;
        min-width: 120px;
        box-shadow: 0 12px 20px -5px rgba(0, 0, 0, 0.35);
    }

    /* 候選人座號小卡片 */
    .candidate-card {
        background: #f8fafc;
        border: 2px solid #e2e8f0;
        border-radius: 16px;
        padding: 12px 8px;
        text-align: center;
        margin-bottom: 10px;
        transition: all 0.2s ease;
    }

    .candidate-card.priority {
        border-color: #fcd34d;
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
        background: #facc15;
        color: #0f172a;
        font-size: 0.72rem;
        font-weight: 900;
        padding: 2px 8px;
        border-radius: 999px;
        margin-top: 4px;
    }

    .badge-1x {
        display: inline-block;
        background: #e2e8f0;
        color: #475569;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 999px;
        margin-top: 4px;
    }

    /* 學生手機端置中卡片 */
    .student-header {
        background: #4f46e5;
        color: white;
        border-radius: 24px 24px 0 0;
        padding: 24px;
        text-align: center;
    }

    .student-body {
        background: white;
        border: 1px solid #e2e8f0;
        border-top: none;
        border-radius: 0 0 24px 24px;
        padding: 28px 24px;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.08);
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==========================================
# 2. 全班共用記憶體資料庫（取代 Firebase，零設定跨裝置同步）
# ==========================================
@st.cache_resource
def get_shared_classroom_state():
    return {
        "lock": threading.Lock(),
        "course_title": "課堂即時搶答抽籤",
        "round_id": 1,
        "is_open": True,
        "candidates": {},       # {"05": {"number": "05", "joined_at": 1710000000}}
        "picked_history": {},   # {"05": 2, "12": 1}
        "last_winners": [],     # ["05", "18"]
    }


state = get_shared_classroom_state()
DEFAULT_PIN = "1234"


# ==========================================
# 3. 核心演算法與輔助函式
# ==========================================
def pick_weighted_candidates(candidates_dict, picked_history, count, weighted=True):
    """執行加權或均等亂數抽籤（未曾抽中者 3x 權重，已抽中過 1x）"""
    pool = list(candidates_dict.values())
    selected = []
    pick_total = min(count, len(pool))

    for _ in range(pick_total):
        if weighted:
            weights = [3 if picked_history.get(item["number"], 0) == 0 else 1 for item in pool]
        else:
            weights = [1 for _ in pool]

        chosen = random.choices(pool, weights=weights, k=1)[0]
        selected.append(chosen["number"])
        pool = [item for item in pool if item["number"] != chosen["number"]]

    return selected


def generate_qr_base64(url_text):
    """產生學生掃碼用 QR Code 圖片（Base64 內嵌）"""
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ==========================================
# 4. 網址參數路由（?mode=admin 與預設學生端）與頂部切換列
# ==========================================
query_mode = st.query_params.get("mode", "student")
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "admin" if query_mode == "admin" else "student"

if "admin_unlocked" not in st.session_state:
    st.session_state.admin_unlocked = False

if "draw_mode" not in st.session_state:
    st.session_state.draw_mode = "weighted"

if "draw_count" not in st.session_state:
    st.session_state.draw_count = 1

if "student_saved_num" not in st.session_state:
    st.session_state.student_saved_num = ""

if "student_submitted_round" not in st.session_state:
    st.session_state.student_submitted_round = 0

# 頂部快速視角切換器（方便老師在單一瀏覽器測試學生與老師雙畫面）
top_col1, top_col2, top_col3 = st.columns([6, 2, 2])
with top_col1:
    st.caption("🔄 **同網址雙模式**：預設為學生手機輸入端；網址加上 `?mode=admin` 即直達老師大螢幕端")
with top_col2:
    if st.button("📱 學生手機端", use_container_width=True, type="primary" if st.session_state.view_mode == "student" else "secondary"):
        st.session_state.view_mode = "student"
        st.query_params.clear()
        st.rerun()
with top_col3:
    if st.button("🖥️ 老師大螢幕端", use_container_width=True, type="primary" if st.session_state.view_mode == "admin" else "secondary"):
        st.session_state.view_mode = "admin"
        st.query_params["mode"] = "admin"
        st.rerun()

st.divider()


# ==========================================
# 5. 老師大螢幕端 (ADMIN VIEW)
# ==========================================
def render_admin_view():
    # --- 4 碼 PIN 碼安全鎖 ---
    if not st.session_state.admin_unlocked:
        _, lock_col, _ = st.columns([1, 1.4, 1])
        with lock_col:
            st.markdown("### 🔒 老師主控台解鎖")
            st.info("請輸入 4 碼教師 PIN 碼以進入抽籤控制台（預設 PIN 碼：`1234`）")
            pin_input = st.text_input("教師 PIN 碼", type="password", max_chars=4, placeholder="••••")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("返回學生端", use_container_width=True):
                    st.session_state.view_mode = "student"
                    st.query_params.clear()
                    st.rerun()
            with c2:
                if st.button("確認解鎖", type="primary", use_container_width=True):
                    if pin_input.strip() == DEFAULT_PIN:
                        st.session_state.admin_unlocked = True
                        st.rerun()
                    else:
                        st.error("PIN 碼錯誤，請重新輸入！")
        return

    # --- 頂部控制列：課程名稱、題次、報名開關、開啟新一題 ---
    h_col1, h_col2, h_col3, h_col4 = st.columns([4, 2, 2.2, 2.5])
    with h_col1:
        st.markdown("🟢 **Streamlit 雲端即時同步中（免外部資料庫）**")
        new_title = st.text_input(
            "課程名稱",
            value=state["course_title"],
            label_visibility="collapsed",
        )
        if new_title.strip() and new_title != state["course_title"]:
            with state["lock"]:
                state["course_title"] = new_title.strip()

    with h_col2:
        st.metric(label="目前進行題次", value=f"第 {state['round_id']} 題")

    with h_col3:
        st.write("")
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

    with h_col4:
        st.write("")
        if st.button("🔄 開啟新一題 / 清空名單", type="primary", use_container_width=True):
            with state["lock"]:
                state["round_id"] += 1
                state["is_open"] = True
                state["candidates"] = {}
                state["last_winners"] = []
            st.toast(f"已開啟第 {state['round_id']} 題，全班手機已自動解鎖！")
            st.rerun()

    # --- 主畫面雙欄：左側抽籤舞台與候選名單（8份） / 右側抽籤設定與 QR Code（4份） ---
    left_col, right_col = st.columns([8, 4], gap="large")

    # ---------------- 左側欄位 ----------------
    with left_col:
        # 1. 抽籤結果聚光燈舞台
        spotlight_placeholder = st.empty()

        def render_spotlight_html(winners_list, rolling=False, total_pool=0):
            if rolling:
                cards_html = "".join([
                    f'<div class="winner-card" style="background:rgba(255,255,255,0.22); color:white; border-color:#fde047;">'
                    f'<span style="font-size:0.75rem;">隨機跳號中</span>'
                    f'<span style="font-size:2.6rem; font-weight:900;">{num}</span></div>'
                    for num in winners_list
                ])
                subtitle = f"🎰 正在從 {total_pool} 位舉手同學中抽出 {len(winners_list)} 位..."
            elif winners_list:
                cards_html = "".join([
                    f'<div class="winner-card">'
                    f'<span style="font-size:0.75rem; font-weight:800; color:#78350f;">中籤座號</span>'
                    f'<span style="font-size:2.8rem; font-weight:900;">{num}</span></div>'
                    for num in winners_list
                ])
                subtitle = "🎉 恭喜以下同學獲得發言機會！"
            else:
                cards_html = (
                    '<div style="color:#c7d2fe; font-size:1.05rem; font-weight:600;">'
                    '等待同學舉手加入名單後，點擊右側「開始公平抽籤」'
                    '</div>'
                    '<div style="color:#a5b4fc; font-size:0.8rem; margin-top:6px;">'
                    '抽中後將自動從本題候選名單移除，並更新加權紀錄'
                    '</div>'
                )
                subtitle = "🎯 本題中籤發言同學"

            return (
                f'<div class="spotlight-stage">'
                f'<div style="font-size:0.95rem; font-weight:800; color:#fde047; margin-bottom:14px;">{subtitle}</div>'
                f'<div class="spotlight-inner">'
                f'<div style="display:flex; flex-wrap:wrap; justify-content:center; gap:12px;">{cards_html}</div>'
                f'</div>'
                f'</div>'
            )

        spotlight_placeholder.markdown(render_spotlight_html(state["last_winners"]), unsafe_allow_html=True)

        # 2. 即時舉手候選名單區（使用 fragment 每 2 秒自動靜默刷新全班最新舉手名單）
        @st.fragment(run_every=2)
        def live_candidate_pool_section():
            candidates = sorted(state["candidates"].values(), key=lambda x: x["joined_at"])
            history = state["picked_history"]

            head_c1, head_c2, head_c3 = st.columns([4.5, 2.8, 2.7])
            with head_c1:
                st.subheader(f"🙋 本題舉手候選名單（{len(candidates)} 人）")
            with head_c2:
                if st.button("✨ 模擬 8 位學生加入", use_container_width=True):
                    sample_pool = ["01", "03", "07", "11", "14", "18", "22", "25", "29", "33", "36", "40"]
                    available = [n for n in sample_pool if n not in state["candidates"]]
                    to_add = random.sample(available, min(8, len(available)))
                    if to_add:
                        with state["lock"]:
                            for idx, num in enumerate(to_add):
                                state["candidates"][num] = {"number": num, "joined_at": time.time() + idx * 0.001}
                        st.rerun()
            with head_c3:
                with st.popover("➕ 手動補登座號", use_container_width=True):
                    manual_num = st.text_input("輸入座號", max_chars=10, key="manual_add_box")
                    if st.button("加入名單", type="primary", use_container_width=True):
                        clean = manual_num.strip().upper()
                        if clean:
                            with state["lock"]:
                                state["candidates"][clean] = {"number": clean, "joined_at": time.time()}
                            st.rerun()

            if st.session_state.draw_mode == "weighted":
                st.info("⚖️ **目前啟用「未曾抽中者優先加權」**：本堂課尚未發言過的同學中籤權重為 **3x 優先**，已發言過為 **1x**。")

            if not candidates:
                st.markdown(
                    """
                    <div style="border:2px dashed #cbd5e1; border-radius:18px; padding:40px 20px; text-align:center; background:#f8fafc; color:#64748b;">
                        <div style="font-weight:700; font-size:0.95rem;">目前還沒有同學舉手加入本題名單</div>
                        <div style="font-size:0.8rem; margin-top:4px;">請學生掃描右側 QR Code 輸入座號，或點擊上方「模擬 8 位學生加入」測試</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                cols = st.columns(4)
                for idx, item in enumerate(candidates):
                    num = item["number"]
                    times = history.get(num, 0)
                    is_priority = (times == 0) and (st.session_state.draw_mode == "weighted")
                    card_cls = "candidate-card priority" if is_priority else "candidate-card"

                    if st.session_state.draw_mode == "weighted":
                        badge_html = (
                            '<span class="badge-3x">3x 優先</span>'
                            if times == 0
                            else f'<span class="badge-1x">1x (已答{times}次)</span>'
                        )
                    else:
                        badge_html = (
                            '<span class="badge-1x" style="background:#dcfce7;color:#166534;">尚未發言</span>'
                            if times == 0
                            else f'<span class="badge-1x">已答{times}次</span>'
                        )

                    with cols[idx % 4]:
                        st.markdown(
                            f"""
                            <div class="{card_cls}">
                                <div class="candidate-num">{num}</div>
                                {badge_html}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if st.button(f"移除 {num}", key=f"del_{num}", use_container_width=True):
                            with state["lock"]:
                                state["candidates"].pop(num, None)
                            st.rerun()

        live_candidate_pool_section()

    # ---------------- 右側欄位 ----------------
    with right_col:
        # 1. 抽籤規則與啟動卡片
        with st.container(border=True):
            st.subheader("🎲 抽籤規則與啟動")
            mode_choice = st.radio(
                "抽籤演算法模式",
                options=["weighted", "equal"],
                format_func=lambda x: "未曾抽中者優先加權（3x 權重，推薦）" if x == "weighted" else "純粹均等亂數（所有人 1x）",
                index=0 if st.session_state.draw_mode == "weighted" else 1,
            )
            if mode_choice != st.session_state.draw_mode:
                st.session_state.draw_mode = mode_choice
                st.rerun()

            st.session_state.draw_count = st.number_input(
                "本題抽取人數（位）",
                min_value=1,
                max_value=10,
                value=st.session_state.draw_count,
                step=1,
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

                    # 播放約 1.5 秒跳號滾動動畫
                    for _ in range(16):
                        fake_sample = [random.choice(pool_nums) for _ in range(len(winners))]
                        spotlight_placeholder.markdown(
                            render_spotlight_html(fake_sample, rolling=True, total_pool=len(pool_nums)),
                            unsafe_allow_html=True,
                        )
                        time.sleep(0.08)

                    # 寫入最終中籤結果：從候選名單移除並累加發言次數
                    with state["lock"]:
                        for w in winners:
                            state["candidates"].pop(w, None)
                            state["picked_history"][w] = state["picked_history"].get(w, 0) + 1
                        state["last_winners"] = winners

                    st.balloons()
                    st.rerun()

        # 2. 學生掃碼加入 QR Code 卡片
        with st.container(border=True):
            st.subheader("📱 學生手機掃碼加入")
            st.caption("部署到 Streamlit Cloud 後，貼上你的正式網址即可生成專屬 QR Code")
            default_app_url = "https://class-draw.streamlit.app/"
            share_url = st.text_input("學生端網址", value=default_app_url, label_visibility="collapsed")
            qr_b64 = generate_qr_base64(share_url)
            st.markdown(
                f"""
                <div style="text-align:center; padding:10px 0;">
                    <img src="data:image/png;base64,{qr_b64}" style="width:165px; height:165px; border-radius:14px; border:2px solid #f1f5f9;" />
                </div>
                """,
                unsafe_allow_html=True,
            )

        # 3. 本堂課已發言紀錄
        with st.container(border=True):
            h_title, h_reset = st.columns([3, 1.5])
            with h_title:
                st.subheader("📊 本堂課已發言紀錄")
            with h_reset:
                if st.button("重置紀錄", use_container_width=True):
                    with state["lock"]:
                        state["picked_history"] = {}
                    st.toast("已重置本堂課發言紀錄，所有人恢復 3x 初始加權")
                    st.rerun()

            if not state["picked_history"]:
                st.caption("尚未抽出任何同學")
            else:
                sorted_hist = sorted(state["picked_history"].items(), key=lambda x: x[1], reverse=True)
                tags_html = " ".join([
                    f'<span style="display:inline-block; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:10px; padding:4px 10px; margin:3px; font-size:0.82rem; font-weight:700;">'
                    f'{num} <span style="background:#e0e7ff; color:#3730a3; padding:1px 6px; border-radius:6px; margin-left:4px;">{cnt}次</span></span>'
                    for num, cnt in sorted_hist
                ])
                st.markdown(tags_html, unsafe_allow_html=True)

        if st.button("🔒 重新鎖定老師控制台", use_container_width=True):
            st.session_state.admin_unlocked = False
            st.rerun()


# ==========================================
# 6. 學生手機端 (STUDENT VIEW)
# ==========================================
@st.fragment(run_every=3)
def render_student_view():
    _, center_col, _ = st.columns([1, 1.6, 1])
    with center_col:
        current_round = state["round_id"]
        is_open = state["is_open"]
        already_submitted = (st.session_state.student_submitted_round == current_round)

        if already_submitted:
            badge_html = '<span style="background:white; color:#4338ca; padding:4px 14px; border-radius:999px; font-size:0.78rem; font-weight:800;">✓ 本題已完成舉手登記</span>'
        elif not is_open:
            badge_html = '<span style="background:#f43f5e; color:white; padding:4px 14px; border-radius:999px; font-size:0.78rem; font-weight:800;">● 本題已截止報名</span>'
        else:
            badge_html = '<span style="background:#34d399; color:#0f172a; padding:4px 14px; border-radius:999px; font-size:0.78rem; font-weight:800;">● 開放舉手搶答中</span>'

        st.markdown(
            f"""
            <div class="student-header">
                <div style="font-size:0.8rem; opacity:0.9; font-weight:700; margin-bottom:4px;">{state['course_title']}</div>
                <div style="font-size:2.2rem; font-weight:900; letter-spacing:-0.02em; margin-bottom:10px;">第 {current_round} 題</div>
                {badge_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            # 狀態 B：本題已送出成功（鎖定防灌水，直到老師開啟下一題自動解鎖）
            if already_submitted:
                st.markdown(
                    f"""
                    <div style="text-align:center; padding:18px 8px;">
                        <div style="font-size:3rem; margin-bottom:8px;">✅</div>
                        <h3 style="margin:0; font-weight:900; color:#0f172a;">已加入第 {current_round} 題候選名單！</h3>
                        <p style="color:#475569; margin:10px 0 18px 0;">
                            你的座號：<span style="background:#eef2ff; color:#4f46e5; font-weight:900; font-size:1.25rem; padding:3px 12px; border-radius:8px;">{st.session_state.student_saved_num}</span>
                        </p>
                        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:14px; padding:14px; font-size:0.82rem; color:#475569; line-height:1.6;">
                            👀 請抬頭看教室大螢幕等待老師抽籤！<br>
                            當老師開啟<strong>下一題</strong>時，此畫面會自動解鎖。
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            # 狀態 C：老師已截止報名
            elif not is_open:
                st.markdown(
                    """
                    <div style="text-align:center; padding:24px 8px;">
                        <div style="font-size:2.8rem; margin-bottom:8px;">⏸️</div>
                        <h3 style="margin:0; font-weight:900; color:#0f172a;">本題已截止舉手報名</h3>
                        <p style="color:#64748b; font-size:0.9rem; margin-top:8px;">老師正在進行抽籤或討論中，請等待老師開啟下一題！</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            # 狀態 A：開放舉手輸入座號
            else:
                st.markdown("**請輸入你的座號**")
                student_num = st.text_input(
                    "座號",
                    value=st.session_state.student_saved_num,
                    max_chars=10,
                    placeholder="例如：05 或 28",
                    label_visibility="collapsed",
                )
                st.caption("系統會自動記住你的號碼，下一題免重新輸入")

                if st.button("🙋 舉手搶答！送出號碼", type="primary", use_container_width=True):
                    clean_num = student_num.strip().upper()
                    if not clean_num:
                        st.warning("請先輸入你的座號！")
                    else:
                        with state["lock"]:
                            state["candidates"][clean_num] = {
                                "number": clean_num,
                                "joined_at": time.time(),
                            }
                        st.session_state.student_saved_num = clean_num
                        st.session_state.student_submitted_round = current_round
                        st.rerun()


# ==========================================
# 7. 主進入點
# ==========================================
if st.session_state.view_mode == "admin":
    render_admin_view()
else:
    render_student_view()