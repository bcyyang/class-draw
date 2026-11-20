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
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1280px;
}

/* 候選人卡片樣式 */
.candidate-card {
    background: #f8fafc;
    border: 2px solid #e2e8f0;
    border-radius: 16px;
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

/* 聚光燈舞台 */
.spotlight-box {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 55%, #0f172a 100%);
    border-radius: 24px;
    padding: 28px 24px;
    color: #ffffff;
    text-align: center;
    box-shadow: 0 12px 28px rgba(30, 27, 75, 0.22);
    margin-bottom: 18px;
}
.spotlight-inner {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 18px;
    padding: 22px 16px;
    min-height: 148px;
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
    min-width: 108px;
    padding: 14px 22px;
    margin: 6px;
    border-radius: 22px;
    background: linear-gradient(180deg, #fde047 0%, #facc15 100%);
    color: #0f172a;
    border: 3px solid #ffffff;
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.25);
}
.rolling-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 96px;
    height: 96px;
    margin: 6px;
    border-radius: 22px;
    background: rgba(255, 255, 255, 0.18);
    border: 2px solid rgba(253, 224, 71, 0.7);
    color: #ffffff;
    font-size: 2.2rem;
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
# 2. 跨全班連線共用記憶體（免外部資料庫）
# ==========================================
DEFAULT_PIN = "1234"


@st.cache_resource
def get_shared_classroom_state():
    """在 Streamlit 伺服器記憶體中建立全班共用的即時狀態池"""
    return {
        "lock": threading.Lock(),
        "course_title": "課堂即時搶答抽籤",
        "round_id": 1,
        "is_open": True,
        "candidates": {},       # {"05": 1710000000.0}
        "picked_history": {},   # {"05": 2, "12": 1}
        "last_winners": [],     # ["05", "18"]
    }


state = get_shared_classroom_state()

# ==========================================
# 3. 核心輔助函式（加權演算法、音效與 QR Code）
# ==========================================
def pick_weighted_candidates(candidates_dict, history_dict, count, weighted=True):
    """加權不放回抽籤：未曾被抽中者權重 3x，已抽中過權重 1x"""
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
        js_code = (
            "<script>(function(){try{"
            "const AudioCtx=window.parent.AudioContext||window.parent.webkitAudioContext||window.AudioContext||window.webkitAudioContext;"
            "const ctx=new AudioCtx();if(ctx.state==='suspended')ctx.resume();"
            "for(let i=0;i<14;i++){const osc=ctx.createOscillator();const gain=ctx.createGain();"
            "osc.type='triangle';osc.frequency.setValueAtTime(480+(i%5)*95,ctx.currentTime+i*0.085);"
            "gain.gain.setValueAtTime(0.14,ctx.currentTime+i*0.085);"
            "gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+i*0.085+0.06);"
            "osc.connect(gain);gain.connect(ctx.destination);"
            "osc.start(ctx.currentTime+i*0.085);osc.stop(ctx.currentTime+i*0.085+0.065);}"
            "}catch(e){}})();//" + str(uid) + "</script>"
        )
    else:
        js_code = (
            "<script>(function(){try{"
            "const AudioCtx=window.parent.AudioContext||window.parent.webkitAudioContext||window.AudioContext||window.webkitAudioContext;"
            "const ctx=new AudioCtx();if(ctx.state==='suspended')ctx.resume();"
            "const notes=[523.25,659.25,783.99,1046.50];"
            "notes.forEach((freq,idx)=>{const osc=ctx.createOscillator();const gain=ctx.createGain();"
            "osc.type='triangle';osc.frequency.setValueAtTime(freq,ctx.currentTime+idx*0.095);"
            "gain.gain.setValueAtTime(0.22,ctx.currentTime+idx*0.095);"
            "gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+idx*0.095+0.32);"
            "osc.connect(gain);gain.connect(ctx.destination);"
            "osc.start(ctx.currentTime+idx*0.095);osc.stop(ctx.currentTime+idx*0.095+0.34);});"
            "}catch(e){}})();//" + str(uid) + "</script>"
        )
    components.html(js_code, height=0, width=0)


def render_spotlight_html(winners, rolling=False, total_pool=0):
    """渲染上方抽籤聚光燈舞台 HTML（無縮排避免 Markdown 誤判為程式碼區塊）"""
    if rolling:
        pills = "".join(f'<div class="rolling-pill">{num}</div>' for num in winners)
        inner = (
            f'<div style="color:#fde047; font-size:0.85rem; font-weight:800; letter-spacing:1px; margin-bottom:10px;">'
            f'🎰 正在從 {total_pool} 位舉手同學中抽出 {len(winners)} 位...</div>'
            f'<div>{pills}</div>'
        )
    elif winners:
        pills = "".join(
            f'<div class="winner-pill">'
            f'<span style="font-size:0.7rem; font-weight:800; color:#78350f;">中籤座號</span>'
            f'<span style="font-size:2.3rem; font-weight:900; line-height:1.1;">{num}</span>'
            f'</div>'
            for num in winners
        )
        inner = (
            f'<div style="color:#fde047; font-size:0.85rem; font-weight:800; letter-spacing:1px; margin-bottom:10px;">'
            f'🎉 恭喜以下同學獲得發言機會！</div>'
            f'<div>{pills}</div>'
        )
    else:
        inner = (
            '<div style="color:#c7d2fe; font-size:1.05rem; font-weight:600;">'
            '等待同學舉手加入名單後，點擊右側「開始公平抽籤」</div>'
            '<div style="color:#a5b4fc; font-size:0.8rem; margin-top:6px;">'
            '抽中後將自動從本題候選名單移除，並更新加權紀錄</div>'
        )

    return (
        '<div class="spotlight-box">'
        '<div style="text-align:left; font-size:1.15rem; font-weight:800; margin-bottom:14px;">🎯 本題中籤發言同學</div>'
        f'<div class="spotlight-inner">{inner}</div>'
        '</div>'
    )


# ==========================================
# 4. 初始化個人瀏覽器 Session 狀態與網址路由
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

if "sound_enabled" not in st.session_state:
    st.session_state.sound_enabled = True

if "play_fanfare_once" not in st.session_state:
    st.session_state.play_fanfare_once = False

if "student_saved_num" not in st.session_state:
    st.session_state.student_saved_num = ""

if "submitted_round" not in st.session_state:
    st.session_state.submitted_round = 0

if "student_url_input" not in st.session_state:
    st.session_state.student_url_input = "https://bcyyang-class-draw.streamlit.app/"

# ==========================================
# 5. 頂部視角切換列（方便老師單機測試雙端）
# ==========================================
nav_col1, nav_col2, nav_col3 = st.columns([6, 2, 2])
with nav_col1:
    st.caption("💡 同網址雙模式：預設為學生手機端；網址加上 `?mode=admin` 即直達老師大螢幕端")
with nav_col2:
    if st.button(
        "📱 學生手機端",
        use_container_width=True,
        type="primary" if st.session_state.view_mode == "student" else "secondary",
    ):
        st.session_state.view_mode = "student"
        st.query_params.clear()
        st.rerun()
with nav_col3:
    if st.button(
        "🖥️ 老師大螢幕端",
        use_container_width=True,
        type="primary" if st.session_state.view_mode == "admin" else "secondary",
    ):
        st.session_state.view_mode = "admin"
        st.query_params["mode"] = "admin"
        st.rerun()

st.divider()

# ==========================================
# 6. 老師大螢幕端 (ADMIN VIEW)
# ==========================================
if st.session_state.view_mode == "admin":

    # --- PIN 碼安全鎖 ---
    if not st.session_state.admin_unlocked:
        _, lock_col, _ = st.columns([1, 1.4, 1])
        with lock_col:
            st.markdown("### 🔒 老師主控台解鎖")
            st.info("請輸入 4 碼教師 PIN 碼以操作抽籤控制台（預設 PIN 碼：**`1234`**）")
            pin_val = st.text_input("教師 PIN 碼", type="password", max_chars=4, placeholder="請輸入 1234")
            if st.button("確認解鎖", type="primary", use_container_width=True):
                if pin_val.strip() == DEFAULT_PIN:
                    st.session_state.admin_unlocked = True
                    st.rerun()
                else:
                    st.error("PIN 碼錯誤，請重新輸入！")
        st.stop()

    # --- 頂部課程標題與開題控制列 ---
    top_c1, top_c2, top_c3, top_c4 = st.columns([4.2, 1.8, 2, 2])
    with top_c1:
        new_title = st.text_input(
            "課程名稱（可直接點擊修改）",
            value=state["course_title"],
            label_visibility="collapsed",
        )
        if new_title.strip() and new_title != state["course_title"]:
            with state["lock"]:
                state["course_title"] = new_title.strip()
        st.markdown(f"## {state['course_title']}")

    with top_c2:
        st.metric(label="目前進行題次", value=f"第 {state['round_id']} 題")

    with top_c3:
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

    with top_c4:
        st.write("")
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

    # --- 主畫面雙欄：左側抽籤舞台與候選名單（8份） / 右側抽籤設定與 QR Code（4份） ---
    left_col, right_col = st.columns([8, 4], gap="large")

    # ---------------- 左側欄位 ----------------
    with left_col:
        spotlight_placeholder = st.empty()
        spotlight_placeholder.markdown(
            render_spotlight_html(state["last_winners"], rolling=False),
            unsafe_allow_html=True,
        )

        # 即時候選名單區（使用 fragment 每 2 秒自動同步全班手機送出的名單）
        @st.fragment(run_every=2)
        def live_candidate_board():
            candidates = state["candidates"]
            history = state["picked_history"]
            sorted_nums = sorted(candidates.keys(), key=lambda k: candidates[k])

            head_c1, head_c2, head_c3 = st.columns([4, 3, 3])
            with head_c1:
                st.markdown(f"### 🙋 本題舉手候選名單（**{len(sorted_nums)} 人**）")
            with head_c2:
                if st.button("✨ 模擬 8 位學生加入", use_container_width=True):
                    sample_pool = ["01", "03", "07", "11", "14", "18", "22", "25", "29", "33", "36", "40"]
                    available = [n for n in sample_pool if n not in state["candidates"]]
                    to_add = random.sample(available, min(8, len(available)))
                    with state["lock"]:
                        now_ts = time.time()
                        for idx, num in enumerate(to_add):
                            state["candidates"][num] = now_ts + idx * 0.01
                    st.rerun()
            with head_c3:
                manual_col1, manual_col2 = st.columns([2, 1])
                with manual_col1:
                    manual_num = st.text_input(
                        "手動補登座號",
                        placeholder="手動座號",
                        label_visibility="collapsed",
                        key="manual_add_box",
                    )
                with manual_col2:
                    if st.button("➕", help="手動加入座號", use_container_width=True):
                        clean = manual_num.strip().upper()
                        if clean:
                            with state["lock"]:
                                state["candidates"][clean] = time.time()
                            st.rerun()

            if st.session_state.draw_mode == "weighted":
                st.info("⚖️ **目前啟用「未曾抽中者優先加權」**：本堂課尚未發言過的同學中籤權重為 **3x 優先**，已發言過為 **1x**。")

            if not sorted_nums:
                st.markdown(
                    """
                    <div style="border:2px dashed #cbd5e1; border-radius:18px; padding:36px 16px; text-align:center; background:#f8fafc; color:#64748b;">
                        <div style="font-weight:700; font-size:0.95rem;">目前還沒有同學舉手加入本題名單</div>
                        <div style="font-size:0.8rem; margin-top:4px;">請學生掃描右側 QR Code 輸入座號，或點擊上方「模擬 8 位學生加入」測試</div>
                    </div>
                    """,
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

    # ---------------- 右側欄位 ----------------
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

                    # 啟動約 1.3 秒跳號滾動音效與視覺動畫
                    play_sound_effect("rolling", enabled=st.session_state.sound_enabled)

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

        # 2. 學生掃碼 QR Code 卡片
        with st.container(border=True):
            st.markdown("#### 📱 學生手機掃碼加入")
            st.caption("掃描下方 QR Code 免登入直接輸入座號（請貼上你的 Streamlit 公開網址以更新二維碼）")
            share_url = st.text_input(
                "學生端網址",
                value=st.session_state.student_url_input,
                label_visibility="collapsed",
            )
            st.session_state.student_url_input = share_url
            if share_url.strip():
                qr_b64 = generate_qr_base64(share_url.strip())
                st.markdown(
                    f'<div style="text-align:center; padding:8px 0;"><img src="data:image/png;base64,{qr_b64}" width="165" style="border-radius:12px; border:1px solid #e2e8f0; padding:6px; background:#fff;"/></div>',
                    unsafe_allow_html=True,
                )

        # 3. 本堂課已發言紀錄（加權依據）
        with st.container(border=True):
            h_col1, h_col2 = st.columns([3, 1.5])
            with h_col1:
                st.markdown("#### 📊 本堂課已發言紀錄")
            with h_col2:
                if st.button("重置紀錄", use_container_width=True):
                    with state["lock"]:
                        state["picked_history"] = {}
                    st.toast("已重置本堂課發言紀錄，所有人恢復 3x 初始加權")
                    st.rerun()

            st.caption("系統會自動記錄已抽中過的座號，作為「未曾抽中者 3x 加權」的計算依據。")
            if not state["picked_history"]:
                st.caption("_尚未抽出任何同學_")
            else:
                sorted_hist = sorted(state["picked_history"].items(), key=lambda x: -x[1])
                badges = " ".join(f"`{num} ({cnt}次)`" for num, cnt in sorted_hist)
                st.markdown(badges)


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
                if already_submitted:
                    st.success(f"✅ 已加入第 **{current_round}** 題候選名單！")
                    st.markdown(f"你的登記座號：**`{st.session_state.student_saved_num}`**")
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
                        clean_num = num_input.strip().upper()
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