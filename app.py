import io
import os
import csv
import json
import time
import random
import base64
import threading
from datetime import datetime
from PIL import Image, ImageDraw
import streamlit as st
import streamlit.components.v1 as components
import qrcode

# ==========================================
# 0. 產生專屬手機桌面捷徑與分頁小圖示 (App Icon)
# ==========================================
@st.cache_data
def generate_custom_app_icon():
    """繪製高辨識度「課堂搶答 × 座次計分」圓角 App 圖示（回傳 PIL Image 與 Base64 PNG）"""
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. 深靛藍圓角底框 (#1e1b4b) 與金邊 (#facc15)
    draw.rounded_rectangle([8, 8, size - 8, size - 8], radius=56, fill="#1e1b4b", outline="#facc15", width=8)

    # 2. 中央金色標靶同心圓（象徵搶答與精準點名）
    cx, cy = size // 2, size // 2 + 6
    draw.ellipse([cx - 78, cy - 78, cx + 78, cy + 78], fill="#312e81", outline="#fde047", width=8)
    draw.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill="#4f46e5", outline="#ffffff", width=6)
    draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill="#facc15")

    # 3. 右上角亮金色加分徽章（象徵 +1 記分）
    bx, by, br = 194, 62, 34
    draw.ellipse([bx - br, by - br, bx + br, by + br], fill="#facc15", outline="#ffffff", width=5)
    # 繪製加號 "+"
    draw.rectangle([bx - 14, by - 4, bx + 14, by + 4], fill="#0f172a")
    draw.rectangle([bx - 4, by - 14, bx + 4, by + 14], fill="#0f172a")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    return img, b64_str


APP_ICON_IMAGE, APP_ICON_B64 = generate_custom_app_icon()

# ==========================================
# 1. 頁面設定與全域自訂 CSS 樣式（完整保留原始視覺風格）
# ==========================================
st.set_page_config(
    page_title="課堂搶答記分",
    page_icon=APP_ICON_IMAGE,
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    /* 防止手機與平板在連續快速點擊加分時觸發「雙擊縮放畫面」並消除點擊延遲 */
    html, body, button, [role="button"], input, .seat-card-box, .seat-card-empty {
        touch-action: manipulation !important;
        -ms-touch-action: manipulation !important;
        -webkit-tap-highlight-color: transparent;
    }
    /* 確保手機與平板在放大畫面時可以順暢上下滑動到底，不被視窗鎖住 */
    html, body, [data-testid="stAppViewContainer"], .main {
        overflow-y: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }
    /* 保留足夠頂部與底部安全距離，避免放大或滑動到底部時被工具列遮擋 */
    .block-container {
        padding-top: 3.2rem !important;
        padding-bottom: 5.5rem !important;
        max-width: 1400px;
    }
    /* 聚光燈舞台外框 */
    .spotlight-box {
        background: linear-gradient(135deg, #312e81 0%, #1e1b4b 55%, #0f172a 100%);
        border-radius: 24px;
        padding: 22px 26px;
        color: #ffffff;
        box-shadow: 0 14px 30px rgba(30, 27, 75, 0.22);
        margin-bottom: 14px;
    }
    /* 聚光燈內部固定高度容器（避免抽籤前後跳動） */
    .spotlight-inner {
        min-height: 248px;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 18px;
        padding: 20px 16px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
    }
    /* 中籤同學金色卡片 */
    .winner-pill {
        background: linear-gradient(180deg, #fde047 0%, #facc15 100%);
        color: #0f172a;
        border: 3px solid #ffffff;
        border-radius: 22px;
        padding: 14px 24px;
        min-width: 138px;
        margin: 6px;
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.28);
    }
    /* 抽籤滾動跳號卡片 */
    .rolling-pill {
        background: rgba(255, 255, 255, 0.18);
        color: #ffffff;
        border: 2px solid rgba(253, 224, 71, 0.75);
        border-radius: 20px;
        width: 112px;
        height: 112px;
        margin: 6px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 2.8rem;
        font-weight: 900;
    }
    /* 候選人座號卡片 */
    .candidate-card {
        background: #f8fafc;
        border: 2px solid #e2e8f0;
        border-radius: 16px;
        padding: 12px 8px;
        text-align: center;
        margin-bottom: 10px;
        transition: all 0.2s ease;
    }
    .candidate-card.weighted-top {
        background: #fffbeb;
        border-color: #fcd34d;
    }
    .candidate-num {
        font-size: 1.9rem;
        font-weight: 900;
        color: #0f172a;
        line-height: 1.15;
        margin-bottom: 4px;
    }
    .badge-3x {
        display: inline-block;
        background: #facc15;
        color: #0f172a;
        font-size: 0.75rem;
        font-weight: 900;
        padding: 2px 9px;
        border-radius: 999px;
    }
    .badge-1x {
        display: inline-block;
        background: #e2e8f0;
        color: #475569;
        font-size: 0.74rem;
        font-weight: 700;
        padding: 2px 9px;
        border-radius: 999px;
    }
    /* 學生手機端頂部橫幅 */
    .student-header {
        background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%);
        color: #ffffff;
        border-radius: 20px;
        padding: 22px 16px;
        text-align: center;
        margin-bottom: 14px;
        box-shadow: 0 10px 24px rgba(79, 70, 229, 0.25);
    }
    .status-open {
        display: inline-block;
        background: #34d399;
        color: #064e3b;
        font-size: 0.82rem;
        font-weight: 900;
        padding: 4px 14px;
        border-radius: 999px;
        margin-top: 10px;
    }
    .status-closed {
        display: inline-block;
        background: #f43f5e;
        color: #ffffff;
        font-size: 0.82rem;
        font-weight: 900;
        padding: 4px 14px;
        border-radius: 999px;
        margin-top: 10px;
    }
    /* 2.0 座次表專屬樣式（觸控友善、清楚顯示班級/座號/姓名/總分） */
    .seat-card-box {
        border-radius: 14px;
        padding: 8px 6px 6px 6px;
        text-align: center;
        border: 2px solid #cbd5e1;
        background: #ffffff;
        margin-bottom: 4px;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
    }
    .seat-card-box.has-score {
        background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%);
        border-color: #f59e0b;
    }
    .seat-card-empty {
        border-radius: 14px;
        padding: 18px 6px;
        text-align: center;
        border: 1.5px dashed #cbd5e1;
        background: #f8fafc;
        color: #94a3b8;
        font-size: 0.8rem;
        font-weight: 700;
        min-height: 112px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        margin-bottom: 4px;
    }
    .podium-banner {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        color: #f8fafc;
        text-align: center;
        font-size: 1.15rem;
        font-weight: 900;
        letter-spacing: 0.35em;
        padding: 12px 24px;
        border-radius: 16px;
        margin: 14px auto 4px auto;
        max-width: 480px;
        box-shadow: 0 6px 16px rgba(15, 23, 42, 0.18);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 允許雙指自由縮放與上下捲動到底（連點雙擊縮放已由上方 touch-action: manipulation 防護），並注入手機桌面捷徑專屬圖示
components.html(
    f"""
    <script>
    (function() {{
        try {{
            const doc = window.parent.document;
            let meta = doc.querySelector('meta[name="viewport"]');
            if (!meta) {{
                meta = doc.createElement('meta');
                meta.name = 'viewport';
                doc.head.appendChild(meta);
            }}
            meta.setAttribute('content', 'width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes');

            // 注入手機「加入主畫面 / 桌面捷徑」專用圖示 (iOS Safari 與 Android Chrome)
            const iconDataUrl = "data:image/png;base64,{APP_ICON_B64}";
            const relTypes = ["apple-touch-icon", "apple-touch-icon-precomposed", "icon", "shortcut icon"];
            relTypes.forEach((relName) => {{
                let link = doc.querySelector(`link[rel="${{relName}}"]`);
                if (!link) {{
                    link = doc.createElement('link');
                    link.rel = relName;
                    doc.head.appendChild(link);
                }}
                link.href = iconDataUrl;
            }});

            // 設定 iOS 加入主畫面時的乾淨 App 標題
            let appTitleMeta = doc.querySelector('meta[name="apple-mobile-web-app-title"]');
            if (!appTitleMeta) {{
                appTitleMeta = doc.createElement('meta');
                appTitleMeta.name = 'apple-mobile-web-app-title';
                doc.head.appendChild(appTitleMeta);
            }}
            appTitleMeta.content = "課堂搶答記分";
        }} catch (e) {{}}
    }})();
    </script>
    """,
    height=0,
    width=0,
)

# ==========================================
# 2. 全班共用記憶體 + 本機 JSON 持久化狀態
# ==========================================
STATE_FILE = "classroom_state.json"

DEFAULT_CLASSROOM_DATA = {
    "course_title": "課堂即時搶答抽籤",
    "admin_pin": "1234",  # 老師端自訂 PIN 碼（預設 1234，可隨時重設並同步保存）
    "round_id": 1,
    "is_open": True,
    "candidates": {},      # { "05": timestamp }
    "picked_history": {},  # { "05": count }
    "last_winners": [],    # ["05", "18"]
    "scores": {},          # { "05": 4, "18": 2 } 累計合併總分（搶答 + 座次表）
    "round_points": 1,     # 本題預設配分
    "awarded_winners": [], # 本輪已給過分的座號，防止重複誤按
    "auto_award": True,    # 抽中時是否直接自動給分
    "active_slot": "slot_1",  # 目前啟用的班級槽位 ("slot_1" | "slot_2" | "slot_3")
    "rosters": {              # 三個班級獨立名單庫
        "slot_1": {"label": "班級 1", "students": {}},
        "slot_2": {"label": "班級 2", "students": {}},
        "slot_3": {"label": "班級 3", "students": {}},
    },
}


def get_active_roster(state_dict: dict) -> dict:
    """取得目前所選班級的學生名單字典 {seat: info}"""
    rosters = state_dict.get("rosters", {})
    slot = state_dict.get("active_slot", "slot_1")
    return rosters.get(slot, {}).get("students", {})


def get_slot_display_title(state_dict: dict, slot_key: str) -> str:
    """組合班級槽位顯示名稱（優先使用老師自訂的班級名稱，否則自動偵測 CSV 班級或預設標籤）"""
    rosters = state_dict.get("rosters", {})
    slot_data = rosters.get(slot_key, {})
    custom_name = slot_data.get("custom_name", "").strip()
    base_label = slot_data.get("label", f"班級 {slot_key[-1]}")
    students = slot_data.get("students", {})

    if custom_name:
        return f"{custom_name}（{len(students)}人）" if students else f"{custom_name}（未匯入）"

    if not students:
        return f"{base_label}（未匯入）"
    # 統計該名單中最常出現的班級名稱
    class_counts = {}
    for info in students.values():
        cname = info.get("class_name", "").strip()
        if cname:
            class_counts[cname] = class_counts.get(cname, 0) + 1
    top_class = max(class_counts.items(), key=lambda x: x[1])[0] if class_counts else ""
    if top_class:
        return f"{base_label}：{top_class}（{len(students)}人）"
    return f"{base_label}（{len(students)}人）"


def switch_active_class_slot(slot_key: str):
    """立即切換目前上課班級槽位並寫入磁碟"""
    with state["lock"]:
        state["active_slot"] = slot_key
        save_persisted_state(state)
    st.session_state["class_switched_toast"] = f"📚 已切換至：{get_slot_display_title(state, slot_key)}"


def save_slot_custom_name(slot_key: str):
    """儲存老師自訂的班級名稱"""
    input_key = f"custom_name_input_{slot_key}"
    new_name = st.session_state.get(input_key, "").strip()
    with state["lock"]:
        if slot_key in state["rosters"]:
            state["rosters"][slot_key]["custom_name"] = new_name
            save_persisted_state(state)
    st.session_state["class_switched_toast"] = f"✏️ 已更新班級名稱為「{new_name or state['rosters'][slot_key]['label']}」"


def load_persisted_state() -> dict:
    """啟動時從磁碟讀取前一次保留的課堂紀錄（若無檔案則回傳預設值）"""
    data = {
        k: (json.loads(json.dumps(v)) if isinstance(v, (dict, list)) else v)
        for k, v in DEFAULT_CLASSROOM_DATA.items()
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                for k in DEFAULT_CLASSROOM_DATA:
                    if k in saved:
                        data[k] = saved[k]
                # 向下相容：若舊存檔只有單一 roster，自動遷移至 slot_1
                if "rosters" not in saved and isinstance(saved.get("roster"), dict) and saved["roster"]:
                    data["rosters"]["slot_1"]["students"] = saved["roster"]
        except Exception:
            pass
    return data


def save_persisted_state(state_dict: dict):
    """將最新課堂紀錄安全寫入磁碟（排除不可序列化的 threading.Lock）"""
    serializable = {k: state_dict[k] for k in DEFAULT_CLASSROOM_DATA if k in state_dict}
    serializable["_updated_at"] = time.time()
    tmp_file = f"{STATE_FILE}.tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, STATE_FILE)
    except Exception:
        pass


def sync_state_from_disk_if_newer(state_dict: dict):
    """若磁碟存檔有來自其他裝置或背景程序的新更新，立即同步至目前記憶體"""
    if not os.path.exists(STATE_FILE):
        return
    try:
        mtime = os.path.getmtime(STATE_FILE)
        if mtime > state_dict.get("_last_disk_mtime", 0):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                with state_dict["lock"]:
                    for k in DEFAULT_CLASSROOM_DATA:
                        if k in saved:
                            state_dict[k] = saved[k]
                    state_dict["_last_disk_mtime"] = mtime
    except Exception:
        pass


@st.cache_resource
def get_shared_classroom_state():
    loaded = load_persisted_state()
    loaded["lock"] = threading.Lock()
    loaded["_last_disk_mtime"] = os.path.getmtime(STATE_FILE) if os.path.exists(STATE_FILE) else 0
    return loaded


state = get_shared_classroom_state()
sync_state_from_disk_if_newer(state)
# 確保舊快取記憶體物件升級時具備新欄位
if "scores" not in state:
    state["scores"] = {}
if "round_points" not in state:
    state["round_points"] = 1
if "awarded_winners" not in state:
    state["awarded_winners"] = []
if "auto_award" not in state:
    state["auto_award"] = True
if "admin_pin" not in state or not str(state["admin_pin"]).strip():
    state["admin_pin"] = "1234"
if "active_slot" not in state:
    state["active_slot"] = "slot_1"
if "rosters" not in state:
    old_single = state.get("roster", {}) if isinstance(state.get("roster"), dict) else {}
    state["rosters"] = {
        "slot_1": {"label": "班級 1", "students": old_single},
        "slot_2": {"label": "班級 2", "students": {}},
        "slot_3": {"label": "班級 3", "students": {}},
    }

DEFAULT_PIN = "1234"

# ==========================================
# 3. 個人連線裝置狀態 (st.session_state)
# ==========================================
query_mode = st.query_params.get("mode", "")
query_auth = st.query_params.get("auth", "")
query_tab = st.query_params.get("tab", "")

if "view_mode" not in st.session_state:
    st.session_state.view_mode = "admin" if query_mode == "admin" else "student"
elif query_mode == "admin":
    st.session_state.view_mode = "admin"

if "admin_unlocked" not in st.session_state:
    st.session_state.admin_unlocked = (query_auth == "1")
elif query_auth == "1":
    st.session_state.admin_unlocked = True

if "admin_tab" not in st.session_state:
    st.session_state.admin_tab = "seating" if query_tab == "seating" else "draw"  # "draw" (搶答抽籤) | "seating" (全班座次表)
elif query_tab in ("draw", "seating"):
    st.session_state.admin_tab = query_tab

if "seating_click_mode" not in st.session_state:
    st.session_state.seating_click_mode = "add"  # "add" (+1分) | "sub" (-1分)
if "seating_undo_stack" not in st.session_state:
    st.session_state.seating_undo_stack = []  # [(seat, delta), ...]
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
if "scoreboard_sort" not in st.session_state:
    st.session_state.scoreboard_sort = "score"  # "score" 或 "seat"
if "history_sort" not in st.session_state:
    st.session_state.history_sort = "count"  # "count" 或 "seat"
if "confirm_new_class" not in st.session_state:
    st.session_state.confirm_new_class = False
if "uploader_reset_ids" not in st.session_state:
    st.session_state.uploader_reset_ids = {"slot_1": 0, "slot_2": 0, "slot_3": 0}
if "round_points_input" not in st.session_state:
    st.session_state.round_points_input = int(state.get("round_points", 1))
if "auto_award_input" not in st.session_state:
    st.session_state.auto_award_input = bool(state.get("auto_award", True))


def sync_round_points_from_widget():
    """當老師點擊本題配分的 +/- 號時平滑同步至共用狀態，不需額外強制 rerun"""
    with state["lock"]:
        state["round_points"] = int(st.session_state.round_points_input)
        save_persisted_state(state)


def sync_auto_award_from_widget():
    """同步自動給分開關狀態"""
    with state["lock"]:
        state["auto_award"] = bool(st.session_state.auto_award_input)
        save_persisted_state(state)


def clear_all_scoreboard_records():
    """透過 on_click 回呼徹底清空全班記分板座號與分數紀錄"""
    with state["lock"]:
        state["scores"] = {}
        state["picked_history"] = {}
        state["awarded_winners"] = []
        state["last_winners"] = []
        save_persisted_state(state)
    st.session_state["confirm_clear_scores_chk"] = False
    st.session_state["scores_cleared_toast"] = True


def reset_entire_classroom():
    """開啟新課堂：一鍵將所有狀態全部重置回到原始狀態"""
    with state["lock"]:
        state["round_id"] = 1
        state["is_open"] = True
        state["candidates"] = {}
        state["picked_history"] = {}
        state["last_winners"] = []
        state["scores"] = {}
        state["awarded_winners"] = []
        save_persisted_state(state)
    st.session_state.seating_undo_stack = []
    st.session_state.confirm_new_class = False
    st.session_state["new_class_toast"] = True


def open_new_class_confirm():
    """開啟新課堂二段確認提示框"""
    st.session_state.confirm_new_class = True


def close_new_class_confirm():
    """取消開啟新課堂二段確認提示框"""
    st.session_state.confirm_new_class = False


# ==========================================
# 4. 核心演算法、音效、CSV 匯出與座次表輔助函式
# ==========================================
def normalize_seat_num(raw_text: str) -> str:
    """標準化座號格式（例如將 '5' 自動補零成 '05'，統一兩位數流水號）"""
    clean = str(raw_text).strip().upper()
    if not clean:
        return ""
    if clean.isdigit() and len(clean) == 1:
        return f"0{clean}"
    return clean


def pick_weighted_candidates(candidates_dict, history_dict, count=1, weighted=True):
    """公平抽籤演算法：未曾抽中者擁有 3x 優先權重"""
    pool = list(candidates_dict.keys())
    selected = []
    pick_total = min(int(count), len(pool))
    for _ in range(pick_total):
        if weighted:
            weights = [3 if history_dict.get(num, 0) == 0 else 1 for num in pool]
        else:
            weights = [1 for _ in pool]
        chosen = random.choices(pool, weights=weights, k=1)[0]
        selected.append(chosen)
        pool.remove(chosen)
    return selected


def generate_qr_base64(url: str) -> str:
    """產生學生端掃碼 QR Code 圖片 Base64"""
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def play_sound_effect(kind="fanfare", enabled=True):
    """透過 Web Audio API 播放抽籤跳號與中獎音效"""
    if not enabled:
        return
    if kind == "rolling":
        js_code = """
        <script>
        (function() {
            try {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                const ctx = new AudioCtx();
                for (let i = 0; i < 12; i++) {
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(480 + (i % 4) * 95, ctx.currentTime + i * 0.095);
                    gain.gain.setValueAtTime(0.10, ctx.currentTime + i * 0.095);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.095 + 0.07);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(ctx.currentTime + i * 0.095);
                    osc.stop(ctx.currentTime + i * 0.095 + 0.07);
                }
            } catch (e) {}
        })();
        </script>
        """
    else:
        js_code = """
        <script>
        (function() {
            try {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                const ctx = new AudioCtx();
                const notes = [523.25, 659.25, 783.99, 1046.50];
                notes.forEach((freq, idx) => {
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.09);
                    gain.gain.setValueAtTime(0.18, ctx.currentTime + idx * 0.09);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.09 + 0.28);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(ctx.currentTime + idx * 0.09);
                    osc.stop(ctx.currentTime + idx * 0.09 + 0.28);
                });
            } catch (e) {}
        })();
        </script>
        """
    components.html(js_code, height=0, width=0)


def build_scores_csv(scores_dict, history_dict, sort_mode="seat", roster_dict=None):
    """產生含 UTF-8 BOM 的成績 CSV 資料（僅列出有加分 > 0 的同學，避免 0 分洗版）"""
    roster = roster_dict or {}
    all_seats = set(scores_dict.keys()) | set(history_dict.keys()) | set(roster.keys())
    items = []
    for seat in all_seats:
        sc = int(scores_dict.get(seat, 0))
        if sc <= 0:
            continue
        info = roster.get(seat, {})
        cls_name = info.get("class_name", "")
        stu_name = info.get("name", "")
        cnt = int(history_dict.get(seat, 0))
        items.append((cls_name, seat, stu_name, sc, cnt))

    if sort_mode == "score":
        items.sort(key=lambda x: (-x[3], int(x[1]) if x[1].isdigit() else 9999, x[1]))
    else:
        items.sort(key=lambda x: (int(x[1]) if x[1].isdigit() else 9999, x[1]))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["座號", "班級", "姓名", "本堂課總分", "發言次數"])

    plain_lines = ["座號\t班級\t姓名\t總分\t發言次數"]
    for cls_name, seat, stu_name, sc, cnt in items:
        writer.writerow([seat, cls_name, stu_name, sc, cnt])
        plain_lines.append(f"{seat}\t{cls_name}\t{stu_name}\t{sc}分\t({cnt}次)")

    if not items:
        plain_lines.append("（目前尚無任何得分紀錄）")

    # 加上 utf-8-sig (BOM) 讓 Excel 雙擊開啟時中文標題不亂碼
    csv_bytes = output.getvalue().encode("utf-8-sig")
    return csv_bytes, "\n".join(plain_lines)


def parse_roster_csv_bytes(raw_bytes: bytes) -> dict:
    """解析班級名單 CSV（欄位需包含：班級、座號、姓名；自動相容 UTF-8 与 Big5/CP950）"""
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("無法辨識 CSV 檔案編碼，請存為 UTF-8 或 Excel CSV 格式。")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 檔案內容為空。")

    # 去除欄位名稱前後空白或 BOM
    clean_fields = [f.strip().lstrip("\ufeff") for f in reader.fieldnames if f]
    required = {"班級", "座號", "姓名"}
    if not required.issubset(set(clean_fields)):
        raise ValueError(f"CSV 標題列必須包含「班級、座號、姓名」，目前偵測到的欄位為：{', '.join(clean_fields)}")

    parsed_roster = {}
    for row in reader:
        clean_row = {(k.strip().lstrip("\ufeff") if k else ""): (v.strip() if v else "") for k, v in row.items()}
        seat = normalize_seat_num(clean_row.get("座號", ""))
        if not seat:
            continue
        parsed_roster[seat] = {
            "class_name": clean_row.get("班級", ""),
            "seat": seat,
            "name": clean_row.get("姓名", ""),
        }

    if not parsed_roster:
        raise ValueError("CSV 檔案中沒有讀取到任何有效的座號資料。")
    return parsed_roster


def generate_sample_roster_csv() -> bytes:
    """產生班級名單 CSV 範本（含班級、座號、姓名三欄）"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["班級", "座號", "姓名"])
    samples = [
        ("華文一甲", "01", "莊子萱"),
        ("華文一甲", "02", "游嘉瑄"),
        ("環安三甲", "03", "周士凱"),
        ("華文一甲", "04", "林士桓"),
        ("光電三乙", "05", "洪嘉均"),
        ("華文一甲", "06", "陳奕愷"),
        ("華文一甲", "07", "彭立雅"),
        ("華文一甲", "08", "林芸函"),
    ]
    for r in samples:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8-sig")


def adjust_seat_score(seat: str, delta: int, record_undo: bool = True):
    """點擊座次表時直接加減該生總分（與搶答抽籤總分共用並同步存檔）"""
    with state["lock"]:
        old_val = int(state["scores"].get(seat, 0))
        new_val = max(0, old_val + delta)
        actual_delta = new_val - old_val
        state["scores"][seat] = new_val
        save_persisted_state(state)

    if record_undo and actual_delta != 0:
        st.session_state.seating_undo_stack.append((seat, actual_delta))
        if len(st.session_state.seating_undo_stack) > 30:
            st.session_state.seating_undo_stack.pop(0)

    stu_info = get_active_roster(state).get(seat, {})
    stu_name = stu_info.get("name", "")
    display_who = f"{seat}號 {stu_name}".strip()
    if actual_delta > 0:
        st.session_state["seating_toast_msg"] = f"⭐ {display_who} +{actual_delta} 分（目前總分 {new_val} 分）"
    elif actual_delta < 0:
        st.session_state["seating_toast_msg"] = f"➖ {display_who} {actual_delta} 分（目前總分 {new_val} 分）"
    else:
        st.session_state["seating_toast_msg"] = f"ℹ️ {display_who} 目前已是 0 分"


def undo_last_seating_click():
    """復原上一筆在座次表的點擊加減分"""
    if not st.session_state.seating_undo_stack:
        return
    seat, last_delta = st.session_state.seating_undo_stack.pop()
    adjust_seat_score(seat, -last_delta, record_undo=False)
    stu_name = get_active_roster(state).get(seat, {}).get("name", "")
    st.session_state["seating_toast_msg"] = f"↩️ 已復原 {seat}號 {stu_name} 的上一筆變動（目前 {state['scores'].get(seat, 0)} 分）"


def render_spotlight_html(winners, rolling=False, total_pool=0, round_points=1, awarded_list=None):
    awarded_set = set(awarded_list or [])
    roster = get_active_roster(state)
    if rolling:
        pills = "".join(f'<div class="rolling-pill">{num}</div>' for num in winners)
        inner = (
            f'<div style="color:#fde047; font-size:0.95rem; font-weight:800; letter-spacing:0.06em; margin-bottom:12px;">'
            f'🎰 正在從 {total_pool} 位舉手同學中抽出 {len(winners)} 位...</div>'
            f'<div style="display:flex; flex-wrap:wrap; justify-content:center; align-items:center;">{pills}</div>'
        )
    elif winners:
        pills_list = []
        for idx, num in enumerate(winners):
            stu_name = roster.get(num, {}).get("name", "")
            name_html = (
                f'<span style="font-size:1.1rem; font-weight:900; color:#1e293b; margin-top:2px;">{stu_name}</span>'
                if stu_name
                else ""
            )
            got_pts = (
                f'<span style="background:#059669; color:#ffffff; font-size:0.76rem; font-weight:900; padding:2px 10px; border-radius:999px; margin-top:4px;">✓ 已加分</span>'
                if num in awarded_set
                else f'<span style="background:rgba(15,23,42,0.12); color:#422006; font-size:0.74rem; font-weight:800; padding:2px 10px; border-radius:999px; margin-top:4px;">待給 {round_points} 分</span>'
            )
            pills_list.append(
                f'<div class="winner-pill">'
                f'<span style="background:#78350f; color:#fef08a; font-size:1.15rem; font-weight:900; padding:4px 18px; border-radius:999px; letter-spacing:0.06em; margin-bottom:6px;">第 {idx + 1} 位</span>'
                f'<span style="font-size:3.5rem; font-weight:900; line-height:1.02; margin-top:2px;">{num}</span>'
                f'{name_html}'
                f'{got_pts}'
                f'</div>'
            )
        pills = "".join(pills_list)
        inner = (
            f'<div style="color:#fde047; font-size:0.98rem; font-weight:800; letter-spacing:0.06em; margin-bottom:10px;">'
            f'🎉 恭喜以下 {len(winners)} 位同學獲得發言機會！（本題配分：{round_points} 分）</div>'
            f'<div style="display:flex; flex-wrap:wrap; justify-content:center; align-items:center;">{pills}</div>'
        )
    else:
        inner = (
            '<div style="color:#e0e7ff; font-size:1.18rem; font-weight:700;">'
            '等待同學舉手加入名單後，點擊右側「開始公平抽籤」</div>'
            '<div style="color:#a5b4fc; font-size:0.86rem; margin-top:6px;">'
            '抽中後將自動從本題候選名單移除，並可依題目難度給予得分</div>'
        )
    return (
        '<div class="spotlight-box">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">'
        f'<span style="font-size:1.2rem; font-weight:900;">🎯 本題中籤發言同學</span>'
        f'<span style="background:rgba(253,224,71,0.2); border:1px solid rgba(253,224,71,0.5); color:#fde047; font-size:0.88rem; font-weight:900; padding:4px 14px; border-radius:999px;">⭐ 本題配分：{round_points} 分</span>'
        f'</div>'
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
        st.query_params.pop("mode", None)
        st.query_params.pop("auth", None)
        st.query_params.pop("tab", None)
        st.rerun()
with nav_col3:
    if st.button(
        "🖥️ 老師端",
        use_container_width=True,
        type="primary" if st.session_state.view_mode == "admin" else "secondary",
    ):
        st.session_state.view_mode = "admin"
        st.query_params["mode"] = "admin"
        if st.session_state.admin_unlocked:
            st.query_params["auth"] = "1"
            st.query_params["tab"] = st.session_state.admin_tab
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
            st.caption("請輸入老師密碼（預設為 `1234`，解鎖後本機連線期間將自動記住）")
            pin_val = st.text_input("請輸入老師密碼", type="password", max_chars=12)
            if st.button("確認解鎖", type="primary", use_container_width=True):
                current_pin = str(state.get("admin_pin", DEFAULT_PIN)).strip()
                if pin_val.strip() == current_pin:
                    st.session_state.admin_unlocked = True
                    st.query_params["mode"] = "admin"
                    st.query_params["auth"] = "1"
                    st.query_params["tab"] = st.session_state.admin_tab
                    st.rerun()
                else:
                    st.error("密碼錯誤，請重新輸入！")

            with st.expander("❓ 忘記密碼？重設為預設密碼 (1234)"):
                st.caption("若忘記先前自訂的老師密碼，可在此將密碼重設回預設值 `1234`（不會清除課堂分數與名單）。")
                if st.button("🔄 重設密碼為 1234", use_container_width=True, key="forgot_reset_pin_btn"):
                    with state["lock"]:
                        state["admin_pin"] = DEFAULT_PIN
                        save_persisted_state(state)
                    st.success("✅ 密碼已重設為 `1234`，請在上方輸入 `1234` 解鎖！")
        st.stop()

    # --- 頂部課程標題與開題控制列（加寬題次與重置題次按鈕，確保清晰可見） ---
    top_c1, top_c2, top_c2_reset, top_c3, top_c4, top_c5, top_c6 = st.columns([2.5, 1.1, 1.1, 1.7, 1.7, 1.3, 1.1])
    with top_c1:
        new_title = st.text_input(
            "課程名稱",
            value=state["course_title"],
            label_visibility="collapsed",
        )
        if new_title.strip() and new_title != state["course_title"]:
            with state["lock"]:
                state["course_title"] = new_title.strip()
                save_persisted_state(state)

    with top_c2:
        st.markdown(
            f'<div style="background:#eef2ff; border:1px solid #c7d2fe; border-radius:10px; padding:6px 8px; text-align:center; font-weight:900; color:#1e1b4b; font-size:1.05rem;">第 {state["round_id"]} 題</div>',
            unsafe_allow_html=True,
        )

    with top_c2_reset:
        if st.button("🔄 題次歸 1", use_container_width=True, help="僅將題次重置回到第 1 題並清空當前名單（保留記分板與發言次數）"):
            with state["lock"]:
                state["round_id"] = 1
                state["is_open"] = True
                state["candidates"] = {}
                state["last_winners"] = []
                state["awarded_winners"] = []
                save_persisted_state(state)
            st.toast("↩️ 已將題次重置回到第 1 題！")
            st.rerun()

    with top_c3:
        reg_label = "🟢 報名開放中（點擊截止）" if state["is_open"] else "🔴 已截止報名（點擊重開）"
        if st.button(reg_label, use_container_width=True):
            with state["lock"]:
                state["is_open"] = not state["is_open"]
                save_persisted_state(state)
            st.rerun()

    with top_c4:
        if st.button("🔄 開啟新一題 / 清空名單", type="primary", use_container_width=True):
            with state["lock"]:
                state["round_id"] += 1
                state["is_open"] = True
                state["candidates"] = {}
                state["last_winners"] = []
                state["awarded_winners"] = []
                save_persisted_state(state)
            st.toast(f"✨ 已開啟第 {state['round_id']} 題！")
            st.rerun()

    with top_c5:
        st.button(
            "🏫 開啟新課堂",
            key="open_new_class_trigger_btn",
            use_container_width=True,
            help="全部重置回到原始狀態（題次歸 1、清空名單、記分板與發言紀錄全部歸零；保留已匯入的三班名單）",
            on_click=open_new_class_confirm,
        )

    with top_c6:
        if st.button("🔑 密碼", use_container_width=True, help="修改老師端密碼或立即鎖定主控台", key="toggle_pin_panel_btn"):
            st.session_state["show_pin_settings"] = not st.session_state.get("show_pin_settings", False)
            st.rerun()

    # 密碼修改與鎖定面板
    if st.session_state.get("show_pin_settings", False):
        with st.container(border=True):
            p_c1, p_c2, p_c3, p_c4 = st.columns([3.2, 2.8, 2.0, 2.0])
            with p_c1:
                st.markdown(f"**🔑 老師主控台密碼設定**（目前密碼：`{state.get('admin_pin', DEFAULT_PIN)}`）")
            with p_c2:
                new_pin_val = st.text_input(
                    "新密碼",
                    placeholder="輸入新密碼（4～12碼）",
                    max_chars=12,
                    label_visibility="collapsed",
                    key="new_admin_pin_input",
                )
            with p_c3:
                if st.button("💾 儲存新密碼", type="primary", use_container_width=True, key="save_new_pin_btn"):
                    clean_pin = new_pin_val.strip()
                    if len(clean_pin) < 4:
                        st.error("密碼至少需 4 碼！")
                    else:
                        with state["lock"]:
                            state["admin_pin"] = clean_pin
                            save_persisted_state(state)
                        st.session_state["show_pin_settings"] = False
                        st.toast(f"✅ 老師密碼已更新為「{clean_pin}」！")
                        st.rerun()
            with p_c4:
                if st.button("🔒 立即鎖定螢幕", use_container_width=True, key="lock_admin_now_btn"):
                    st.session_state.admin_unlocked = False
                    st.session_state["show_pin_settings"] = False
                    st.query_params.pop("auth", None)
                    st.rerun()

    # --- 2.0 雙畫面工作區切換 + 三班名單一鍵切換列 ---
    tab_c1, tab_c2, tab_c3 = st.columns([2.1, 2.2, 5.7])
    with tab_c1:
        if st.button(
            "🎯 搶答抽籤主控台",
            use_container_width=True,
            type="primary" if st.session_state.admin_tab == "draw" else "secondary",
            key="switch_tab_draw_btn",
        ):
            st.session_state.admin_tab = "draw"
            st.query_params["tab"] = "draw"
            st.rerun()
    with tab_c2:
        active_roster_now = get_active_roster(state)
        roster_cnt = len(active_roster_now)
        seating_btn_label = f"🗺️ 全班座次表記分（{roster_cnt}人）" if roster_cnt > 0 else "🗺️ 全班座次表記分"
        if st.button(
            seating_btn_label,
            use_container_width=True,
            type="primary" if st.session_state.admin_tab == "seating" else "secondary",
            key="switch_tab_seating_btn",
        ):
            st.session_state.admin_tab = "seating"
            st.query_params["tab"] = "seating"
            st.rerun()
    with tab_c3:
        slot_keys = ["slot_1", "slot_2", "slot_3"]
        cur_slot = state.get("active_slot", "slot_1")
        if cur_slot not in slot_keys:
            cur_slot = "slot_1"
        s_cols = st.columns(3, gap="small")
        for idx, s_key in enumerate(slot_keys):
            is_cur = (s_key == cur_slot)
            btn_lbl = f"🟢 {get_slot_display_title(state, s_key)}" if is_cur else f"⚪ {get_slot_display_title(state, s_key)}"
            with s_cols[idx]:
                st.button(
                    btn_lbl,
                    key=f"top_quick_switch_{s_key}",
                    use_container_width=True,
                    type="primary" if is_cur else "secondary",
                    on_click=switch_active_class_slot,
                    args=(s_key,),
                )

    # 開啟新課堂防誤按確認橫幅
    if st.session_state.confirm_new_class:
        with st.container(border=True):
            warn_c1, warn_c2, warn_c3 = st.columns([6.4, 1.8, 1.8])
            with warn_c1:
                st.warning("⚠️ 確定要**開啟新課堂**嗎？這將會把**題次歸 1、舉手名單、記分板分數與已發言紀錄全部清空**回到原始狀態！")
            with warn_c2:
                st.button(
                    "✅ 確定全部重置",
                    key="confirm_reset_entire_class_btn",
                    type="primary",
                    use_container_width=True,
                    on_click=reset_entire_classroom,
                )
            with warn_c3:
                st.button(
                    "❌ 取消",
                    key="cancel_reset_entire_class_btn",
                    use_container_width=True,
                    on_click=close_new_class_confirm,
                )

    # 若剛抽完籤，播放一次勝利和弦音效
    if st.session_state.play_fanfare_once:
        play_sound_effect("fanfare", enabled=st.session_state.sound_enabled)
        st.session_state.play_fanfare_once = False

    if st.session_state.pop("scores_cleared_toast", False):
        st.toast("🗑️ 已刪除全部課堂記分板紀錄！")

    if st.session_state.pop("new_class_toast", False):
        st.toast("🏫 已開啟新課堂，所有紀錄已全部重置回到原始狀態！")

    class_switched_toast = st.session_state.pop("class_switched_toast", None)
    if class_switched_toast:
        st.toast(class_switched_toast)

    seating_toast_msg = st.session_state.pop("seating_toast_msg", None)
    if seating_toast_msg:
        st.toast(seating_toast_msg)

    # ========================================================
    # 分頁 B：🗺️ 全班座次表互動記分 (8 列 × 8 欄，由下往上排列)
    # ========================================================
    if st.session_state.admin_tab == "seating":
        roster = get_active_roster(state)
        cur_slot_key = state.get("active_slot", "slot_1")

        # 1. 上方操作與 CSV 匯入工具列
        with st.container(border=True):
            ctrl_c1, ctrl_c2, ctrl_c3, ctrl_c4 = st.columns([2.4, 2.2, 1.8, 3.6])
            with ctrl_c1:
                if st.button(
                    "➕ 目前模式：點擊座位 +1 分",
                    use_container_width=True,
                    type="primary" if st.session_state.seating_click_mode == "add" else "secondary",
                    key="seating_mode_add_btn",
                ):
                    st.session_state.seating_click_mode = "add"
                    st.rerun()
            with ctrl_c2:
                if st.button(
                    "➖ 目前模式：點錯扣分 (-1 分)",
                    use_container_width=True,
                    type="primary" if st.session_state.seating_click_mode == "sub" else "secondary",
                    key="seating_mode_sub_btn",
                ):
                    st.session_state.seating_click_mode = "sub"
                    st.rerun()
            with ctrl_c3:
                undo_len = len(st.session_state.seating_undo_stack)
                st.button(
                    f"↩️ 復原上一筆 ({undo_len})" if undo_len > 0 else "↩️ 復原上一筆",
                    disabled=(undo_len == 0),
                    use_container_width=True,
                    key="seating_undo_btn",
                    on_click=undo_last_seating_click,
                )
            with ctrl_c4:
                csv_bytes, _ = build_scores_csv(
                    state["scores"],
                    state["picked_history"],
                    sort_mode="seat",
                    roster_dict=roster,
                )
                today_str = datetime.now().strftime("%Y%m%d")
                safe_title = "".join(c for c in state["course_title"] if c.isalnum() or c in ("_", "-")) or "課堂成績"
                slot_short_name = get_slot_display_title(state, cur_slot_key).split("（")[0].replace("：", "_")
                st.download_button(
                    label="📥 下載合併總分 Excel/CSV（供助教登記）",
                    data=csv_bytes,
                    file_name=f"{safe_title}_{slot_short_name}_合併成績表_{today_str}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="seating_download_csv_btn",
                )

            with st.expander("📂 管理三個班級的 CSV 名單（分別上傳、永久保存、隨時切換）", expanded=(len(roster) == 0)):
                info_c1, info_c2 = st.columns([7.5, 2.5])
                with info_c1:
                    st.caption("格式說明：CSV 標題列請命名為 **班級、座號、姓名**（共三欄，無需學號）。三個班級各自上傳後會永久保存在系統中，上課時從上方下拉選單切換班級即可。")
                with info_c2:
                    st.download_button(
                        label="📄 下載 CSV 範本",
                        data=generate_sample_roster_csv(),
                        file_name="班級座次表範本.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="download_sample_roster_btn",
                    )

                slot_cols = st.columns(3, gap="medium")
                for idx, s_key in enumerate(["slot_1", "slot_2", "slot_3"]):
                    with slot_cols[idx]:
                        with st.container(border=True):
                            slot_title = get_slot_display_title(state, s_key)
                            is_active_slot = (s_key == cur_slot_key)
                            if is_active_slot:
                                st.markdown(f"**🟢 {slot_title}**（使用中）")
                            else:
                                st.markdown(f"**⚪ {slot_title}**")

                            # 自訂班級名稱輸入框
                            cur_custom = state["rosters"][s_key].get("custom_name", "")
                            st.text_input(
                                f"班級 {idx + 1} 名稱",
                                value=cur_custom,
                                placeholder=f"輸入班級 {idx + 1} 名稱（如：華文一甲）",
                                label_visibility="collapsed",
                                key=f"custom_name_input_{s_key}",
                                on_change=save_slot_custom_name,
                                args=(s_key,),
                            )

                            up_file = st.file_uploader(
                                f"上傳{s_key}名單",
                                type=["csv"],
                                label_visibility="collapsed",
                                key=f"roster_csv_uploader_{s_key}_{st.session_state.uploader_reset_ids.get(s_key, 0)}",
                            )
                            if up_file is not None:
                                if st.button(
                                    f"✅ 確認匯入至班級 {idx + 1}",
                                    type="primary",
                                    use_container_width=True,
                                    key=f"confirm_import_{s_key}_btn",
                                ):
                                    try:
                                        new_roster = parse_roster_csv_bytes(up_file.getvalue())
                                        with state["lock"]:
                                            state["rosters"][s_key]["students"] = new_roster
                                            state["active_slot"] = s_key
                                            save_persisted_state(state)
                                        st.session_state.uploader_reset_ids[s_key] = st.session_state.uploader_reset_ids.get(s_key, 0) + 1
                                        st.toast(f"🎉 已匯入「{get_slot_display_title(state, s_key)}」並自動切換使用！")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"匯入失敗：{e}")

                            b_c1, b_c2 = st.columns(2)
                            with b_c1:
                                if not is_active_slot:
                                    st.button(
                                        "切換使用",
                                        key=f"use_{s_key}_btn",
                                        use_container_width=True,
                                        on_click=switch_active_class_slot,
                                        args=(s_key,),
                                    )
                                else:
                                    st.button("使用中", key=f"using_{s_key}_btn", disabled=True, use_container_width=True)
                            with b_c2:
                                has_data = len(state["rosters"][s_key].get("students", {})) > 0
                                if st.button("清除名單", key=f"clear_{s_key}_btn", disabled=not has_data, use_container_width=True):
                                    with state["lock"]:
                                        state["rosters"][s_key]["students"] = {}
                                        save_persisted_state(state)
                                    st.toast(f"已清除班級 {idx + 1} 名單")
                                    st.rerun()

        # 2. 渲染 8 列 × 8 欄座次表（第 8 排在最上方，第 1 排 01~08 在最下方靠近講台）
        if st.session_state.seating_click_mode == "add":
            st.info("👆 **加分模式啟用中**：直接點擊下方任一位同學的座位按鈕，該生總分即 **+1 分**（電腦與手機每 2 秒自動雙向同步）。")
        else:
            st.warning("👇 **扣分修正模式啟用中**：點擊任一位同學的座位按鈕，該生總分即 **-1 分**（最低 0 分）；修正完畢請切回加分模式。")

        @st.fragment(run_every=2)
        def live_seating_grid():
            sync_state_from_disk_if_newer(state)
            cur_roster = get_active_roster(state)
            is_add_mode = st.session_state.seating_click_mode == "add"
            action_delta = 1 if is_add_mode else -1

            # 由最上排（第 8 排：57~64）往下渲染至最下排（第 1 排：01~08）
            for row_idx in range(7, -1, -1):
                row_cols = st.columns(8, gap="small")
                for col_idx in range(8):
                    seat_int = row_idx * 8 + col_idx + 1
                    seat_str = f"{seat_int:02d}"
                    stu_info = cur_roster.get(seat_str)
                    cur_score = int(state["scores"].get(seat_str, 0))

                    with row_cols[col_idx]:
                        if stu_info:
                            cls_label = stu_info.get("class_name", "") or "　"
                            name_label = stu_info.get("name", "") or "未命名"
                            card_cls = "seat-card-box has-score" if cur_score > 0 else "seat-card-box"
                            score_badge_bg = "#d97706" if cur_score > 0 else "#64748b"
                            st.markdown(
                                f'<div class="{card_cls}">'
                                f'<div style="font-size:0.74rem; font-weight:400; color:#475569; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{cls_label}</div>'
                                f'<div style="font-size:1.3rem; font-weight:500; color:#0f172a; line-height:1.15; margin:2px 0;">{seat_str}</div>'
                                f'<div style="font-size:0.98rem; font-weight:500; color:#1e293b; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{name_label}</div>'
                                f'<div style="margin-top:6px;"><span style="background:{score_badge_bg}; color:#ffffff; font-size:0.95rem; font-weight:800; padding:3px 12px; border-radius:999px; display:inline-block;">⭐ {cur_score} 分</span></div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                            btn_text = f"➕ {seat_str} (+1)" if is_add_mode else f"➖ {seat_str} (-1)"
                            st.button(
                                btn_text,
                                key=f"seat_click_{seat_str}",
                                use_container_width=True,
                                type="primary" if (is_add_mode and cur_score > 0) else "secondary",
                                on_click=adjust_seat_score,
                                args=(seat_str, action_delta, True),
                            )
                        else:
                            # 尚未匯入名單或該座號為空位（仍顯示座號，並支援直接點擊計分）
                            card_cls = "seat-card-box has-score" if cur_score > 0 else "seat-card-empty"
                            if cur_score > 0:
                                st.markdown(
                                    f'<div class="{card_cls}">'
                                    f'<div style="font-size:0.72rem; font-weight:400; color:#64748b;">空位 / 未建檔</div>'
                                    f'<div style="font-size:1.3rem; font-weight:500; color:#0f172a; line-height:1.15; margin:2px 0;">{seat_str}</div>'
                                    f'<div style="margin-top:6px;"><span style="background:#d97706; color:#ffffff; font-size:0.95rem; font-weight:800; padding:3px 12px; border-radius:999px; display:inline-block;">⭐ {cur_score} 分</span></div>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    f'<div class="seat-card-empty"><div style="font-size:1.15rem; font-weight:500; color:#94a3b8;">{seat_str}</div><div>空位</div></div>',
                                    unsafe_allow_html=True,
                                )
                            btn_text = f"➕ {seat_str}" if is_add_mode else f"➖ {seat_str}"
                            st.button(
                                btn_text,
                                key=f"seat_empty_click_{seat_str}",
                                use_container_width=True,
                                on_click=adjust_seat_score,
                                args=(seat_str, action_delta, True),
                            )

        live_seating_grid()

        # 最下方正中央講台標示
        st.markdown('<div class="podium-banner">講　　　　台</div>', unsafe_allow_html=True)
        st.stop()

    # ========================================================
    # 分頁 A：🎯 搶答抽籤主控台（完整保留原本雙欄佈局與全部功能）
    # ========================================================
    left_col, right_col = st.columns([8, 4], gap="large")

    # ---------------- 左側 8 欄：聚光燈 + 給分操作 + 舉手候選名單（每 2 秒局部自動同步） ----------------
    with left_col:

        @st.fragment(run_every=2)
        def live_admin_left_board():
            pts_now = int(state.get("round_points", 1))
            awarded_now = set(state.get("awarded_winners", []))

            spotlight_placeholder = st.empty()
            spotlight_placeholder.markdown(
                render_spotlight_html(
                    state["last_winners"],
                    rolling=False,
                    round_points=pts_now,
                    awarded_list=awarded_now,
                ),
                unsafe_allow_html=True,
            )

            # --- 中籤給分操作條（固定高度佔位，抽籤前後畫面不跳動） ---
            current_winners = list(state.get("last_winners", []))
            with st.container(border=True):
                if current_winners:
                    g_c1, g_c2 = st.columns([2.4, 3.6])
                    with g_c1:
                        st.markdown(f"**⭐ 本題給分（答對 +{pts_now} 分）**")
                        un_awarded = [w for w in current_winners if w not in awarded_now]
                        if un_awarded:
                            if st.button(
                                f"🎉 全部中籤者 +{pts_now} 分",
                                type="primary",
                                use_container_width=True,
                                key="award_all_winners_btn",
                            ):
                                with state["lock"]:
                                    for w in un_awarded:
                                        state["scores"][w] = state["scores"].get(w, 0) + pts_now
                                        if w not in state["awarded_winners"]:
                                            state["awarded_winners"].append(w)
                                    save_persisted_state(state)
                                play_sound_effect("fanfare", enabled=st.session_state.sound_enabled)
                                st.toast(f"⭐ 已為 {', '.join(un_awarded)} 號加上 {pts_now} 分！")
                                st.rerun()
                        else:
                            st.success("✅ 本輪中籤同學皆已完成給分")

                    with g_c2:
                        st.caption("個別給分 / 扣回（可針對單一座號調整本題得分）：")
                        w_cols = st.columns(min(len(current_winners), 5))
                        for idx, w_num in enumerate(current_winners):
                            is_done = w_num in awarded_now
                            btn_label = f"↩️ {w_num}號 (-{pts_now}分)" if is_done else f"➕ {w_num}號 (+{pts_now}分)"
                            with w_cols[idx % 5]:
                                if st.button(
                                    btn_label,
                                    key=f"award_toggle_{w_num}_{idx}",
                                    use_container_width=True,
                                ):
                                    with state["lock"]:
                                        if is_done:
                                            state["scores"][w_num] = max(0, state["scores"].get(w_num, 0) - pts_now)
                                            state["awarded_winners"] = [x for x in state["awarded_winners"] if x != w_num]
                                        else:
                                            state["scores"][w_num] = state["scores"].get(w_num, 0) + pts_now
                                            state["awarded_winners"].append(w_num)
                                        save_persisted_state(state)
                                    play_sound_effect("fanfare", enabled=st.session_state.sound_enabled)
                                    st.rerun()
                else:
                    st.markdown(
                        f'<div style="min-height:76px; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; color:#64748b;">'
                        f'<div style="font-weight:800; font-size:0.95rem; color:#334155;">⭐ 本題給分操作區（答對 +{pts_now} 分）</div>'
                        f'<div style="font-size:0.82rem; margin-top:4px;">抽出中籤同學後，將在此顯示「一鍵全體給分」與「個別給分 / 扣回」按鈕</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            with st.container(border=True):
                candidates = state["candidates"]
                history = state["picked_history"]
                sorted_nums = sorted(candidates.keys(), key=lambda k: candidates[k])

                header_c1, header_c2, header_c3, header_c4, header_c5 = st.columns([3.0, 2.0, 1.8, 1.1, 1.1])
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
                            save_persisted_state(state)
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
                                save_persisted_state(state)
                            st.rerun()
                with header_c5:
                    if st.button("🔄 同步", use_container_width=True, help="立即從伺服器同步最新名單與中籤畫面"):
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
                            cur_pts = state["scores"].get(num, 0)
                            pts_tag = f' · <b style="color:#4f46e5;">{cur_pts}分</b>' if cur_pts > 0 else ""
                            st.markdown(
                                f'<div class="{card_cls}"><div class="candidate-num">{num}</div>{badge_html}<div style="font-size:0.72rem; color:#64748b; margin-top:3px;">累計{pts_tag if pts_tag else " 0分"}</div></div>',
                                unsafe_allow_html=True,
                            )

            return spotlight_placeholder

        spotlight_placeholder = live_admin_left_board()

    # ---------------- 右側 4 欄：抽籤規則 + 課堂記分板 + 已發言紀錄 + QR Code ----------------
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

            cfg_c1, cfg_c2 = st.columns(2)
            with cfg_c1:
                st.number_input(
                    "抽取人數（位）",
                    min_value=1,
                    max_value=50,
                    step=1,
                    key="draw_count",
                )
            with cfg_c2:
                st.number_input(
                    "本題配分（分）",
                    min_value=1,
                    max_value=50,
                    step=1,
                    key="round_points_input",
                    on_change=sync_round_points_from_widget,
                    help="依題目難度設定本題答對可得幾分（例如簡單題 1 分、挑戰題 2~5 分）",
                )

            st.toggle(
                "⚡ 抽中時自動加上本題配分",
                key="auto_award_input",
                on_change=sync_auto_award_from_widget,
                help="開啟後，抽出中籤同學時會立刻將本題配分加入記分板；若答錯可於左側點按扣回",
            )

            st.toggle(
                "🔊 啟用抽籤跳號與中獎音效",
                key="sound_enabled",
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
                    pts_val = int(st.session_state.round_points_input)
                    auto_give = bool(st.session_state.auto_award_input)

                    play_sound_effect("rolling", enabled=st.session_state.sound_enabled)

                    for _ in range(15):
                        fake_sample = [random.choice(pool_nums) for _ in range(len(winners))]
                        spotlight_placeholder.markdown(
                            render_spotlight_html(
                                fake_sample,
                                rolling=True,
                                total_pool=len(pool_nums),
                                round_points=pts_val,
                            ),
                            unsafe_allow_html=True,
                        )
                        time.sleep(0.085)

                    with state["lock"]:
                        state["round_points"] = pts_val
                        for w in winners:
                            state["candidates"].pop(w, None)
                            state["picked_history"][w] = state["picked_history"].get(w, 0) + 1
                            if auto_give:
                                state["scores"][w] = state["scores"].get(w, 0) + pts_val
                            else:
                                state["scores"].setdefault(w, 0)
                        state["last_winners"] = winners
                        state["awarded_winners"] = list(winners) if auto_give else []
                        save_persisted_state(state)

                    st.session_state.play_fanfare_once = True
                    st.rerun()

        # 2. 🏆 課堂即時記分板（支援依得分排名 / 依座號排序 + 手動加扣分微調）
        @st.fragment(run_every=2)
        def live_admin_scoreboard_card():
            sync_state_from_disk_if_newer(state)
            with st.container(border=True):
                st.markdown("#### 🏆 課堂即時記分板")

                sort_c1, sort_c2 = st.columns(2)
                with sort_c1:
                    if st.button(
                        "🥇 依得分排名",
                        use_container_width=True,
                        type="primary" if st.session_state.scoreboard_sort == "score" else "secondary",
                        key="sort_by_score_btn",
                    ):
                        st.session_state.scoreboard_sort = "score"
                        st.rerun()
                with sort_c2:
                    if st.button(
                        "🔢 依座號排序",
                        use_container_width=True,
                        type="primary" if st.session_state.scoreboard_sort == "seat" else "secondary",
                        key="sort_by_seat_btn",
                    ):
                        st.session_state.scoreboard_sort = "seat"
                        st.rerun()

                # 合併所有出現過的座號（有分數者 + 曾被抽中者）
                all_seats = set(state["scores"].keys()) | set(state["picked_history"].keys())
                score_items = [(seat, state["scores"].get(seat, 0)) for seat in all_seats]

                if not score_items:
                    st.markdown(
                        '<div style="padding:14px 12px; border-radius:12px; background:#f8fafc; border:1px dashed #cbd5e1; color:#94a3b8; font-size:0.88rem; text-align:center; margin-top:6px;">尚無得分紀錄（抽中同學並給分後將自動顯示於此）</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    if st.session_state.scoreboard_sort == "score":
                        # 依分數由高到低排序，同分則依座號由小到大
                        score_items.sort(key=lambda x: (-x[1], int(x[0]) if x[0].isdigit() else 9999, x[0]))
                    else:
                        # 依座號由小到大排序
                        score_items.sort(key=lambda x: (int(x[0]) if x[0].isdigit() else 9999, x[0]))

                    # 計算名次（同分同名次）
                    unique_desc_scores = sorted({sc for _, sc in score_items if sc > 0}, reverse=True)
                    rows_html = []
                    for seat, sc in score_items:
                        if st.session_state.scoreboard_sort == "score":
                            if sc > 0 and sc in unique_desc_scores:
                                rank = unique_desc_scores.index(sc) + 1
                                if rank == 1:
                                    prefix = '<span style="font-size:1.1rem;">🥇</span>'
                                elif rank == 2:
                                    prefix = '<span style="font-size:1.1rem;">🥈</span>'
                                elif rank == 3:
                                    prefix = '<span style="font-size:1.1rem;">🥉</span>'
                                else:
                                    prefix = f'<span style="font-size:0.8rem; font-weight:800; color:#64748b; min-width:22px; text-align:center;">#{rank}</span>'
                            else:
                                prefix = '<span style="font-size:0.8rem; font-weight:700; color:#94a3b8; min-width:22px; text-align:center;">-</span>'
                        else:
                            prefix = '<span style="font-size:0.8rem; font-weight:800; color:#6366f1;">座號</span>'

                        bg_style = "background:#fffbeb; border-color:#fcd34d;" if (sc > 0 and unique_desc_scores and sc == unique_desc_scores[0]) else "background:#f8fafc; border-color:#e2e8f0;"
                        stu_name_tag = get_active_roster(state).get(seat, {}).get("name", "")
                        display_seat_label = f"{seat} 號 {stu_name_tag}".strip()
                        rows_html.append(
                            f'<div style="display:flex; align-items:center; justify-content:space-between; {bg_style} border:1.5px solid; border-radius:12px; padding:7px 12px; margin-top:6px;">'
                            f'<div style="display:flex; align-items:center; gap:8px;">{prefix}<span style="font-size:1.1rem; font-weight:900; color:#0f172a;">{display_seat_label}</span></div>'
                            f'<div style="background:#4f46e5; color:#ffffff; font-size:0.95rem; font-weight:900; padding:2px 12px; border-radius:999px;">{sc} 分</div>'
                            f'</div>'
                        )

                    st.markdown(
                        f'<div style="max-height:300px; overflow-y:auto; padding-right:2px;">{"".join(rows_html)}</div>',
                        unsafe_allow_html=True,
                    )

                    # --- 助教成績匯出區 (CSV 下載 + 快速複製文字版) ---
                    csv_bytes, plain_summary = build_scores_csv(
                        state["scores"],
                        state["picked_history"],
                        sort_mode=st.session_state.scoreboard_sort,
                        roster_dict=get_active_roster(state),
                    )
                    today_str = datetime.now().strftime("%Y%m%d")
                    safe_title = "".join(c for c in state["course_title"] if c.isalnum() or c in ("_", "-")) or "課堂成績"
                    st.download_button(
                        label="📥 下載成績 Excel/CSV（供助教登記）",
                        data=csv_bytes,
                        file_name=f"{safe_title}_成績表_{today_str}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        type="primary",
                        key="download_scores_csv_btn",
                    )
                    with st.expander("📋 快速複製文字版成績（貼上 LINE / 試算表）"):
                        st.code(plain_summary, language="text")

                # 手動補加 / 扣分微調列
                with st.expander("✏️ 手動補加 / 扣分微調"):
                    adj_c1, adj_c2, adj_c3 = st.columns([1.4, 1.3, 1.3])
                    with adj_c1:
                        adj_seat = st.text_input("座號", placeholder="如 05", label_visibility="collapsed", key="adj_seat_box")
                    with adj_c2:
                        adj_delta = st.number_input("加減分", min_value=-20, max_value=50, value=1, step=1, label_visibility="collapsed", key="adj_delta_box")
                    with adj_c3:
                        if st.button("套用", use_container_width=True, key="apply_adj_score_btn"):
                            clean_s = normalize_seat_num(adj_seat)
                            if clean_s:
                                with state["lock"]:
                                    new_val = max(0, state["scores"].get(clean_s, 0) + int(adj_delta))
                                    state["scores"][clean_s] = new_val
                                    save_persisted_state(state)
                                st.toast(f"已調整 {clean_s} 號分數（目前 {new_val} 分）")
                                st.rerun()

                    st.divider()
                    confirm_clear_scores = st.checkbox(
                        "確認要刪除全部記分板紀錄（此動作無法復原）",
                        key="confirm_clear_scores_chk",
                    )
                    st.button(
                        "🗑️ 刪除全部記分板紀錄",
                        disabled=not confirm_clear_scores,
                        use_container_width=True,
                        key="clear_all_scores_btn",
                        on_click=clear_all_scoreboard_records,
                    )

        live_admin_scoreboard_card()

        # 3. 本堂課已發言紀錄卡片
        def live_admin_history_card():
            with st.container(border=True):
                hist_h1, hist_h2 = st.columns([2.6, 1.4])
                with hist_h1:
                    st.markdown("#### 📊 本堂課已發言紀錄")
                with hist_h2:
                    if st.button("🗑️ 重置紀錄", use_container_width=True, help="清空所有已發言紀錄，所有人恢復 3x 優先權重"):
                        with state["lock"]:
                            state["picked_history"] = {}
                            save_persisted_state(state)
                        st.toast("已清空本堂課已發言紀錄，所有人恢復 3x 優先加權！")
                        st.rerun()

                st.caption("作為「未曾抽中者 3x 加權」的依據；下課或換班時可點右上角重置。")

                h_sort_c1, h_sort_c2 = st.columns(2)
                with h_sort_c1:
                    if st.button(
                        "🔥 依發言次數排序",
                        use_container_width=True,
                        type="primary" if st.session_state.history_sort == "count" else "secondary",
                        key="hist_sort_by_count_btn",
                    ):
                        st.session_state.history_sort = "count"
                        st.rerun()
                with h_sort_c2:
                    if st.button(
                        "🔢 依座號排序",
                        use_container_width=True,
                        type="primary" if st.session_state.history_sort == "seat" else "secondary",
                        key="hist_sort_by_seat_btn",
                    ):
                        st.session_state.history_sort = "seat"
                        st.rerun()

                if not state["picked_history"]:
                    st.markdown(
                        '<div style="padding:14px 12px; border-radius:12px; background:#f8fafc; border:1px dashed #cbd5e1; color:#94a3b8; font-size:0.9rem; text-align:center; margin-top:6px;">尚未抽出任何同學</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    if st.session_state.history_sort == "seat":
                        sorted_hist = sorted(
                            state["picked_history"].items(),
                            key=lambda x: (int(x[0]) if x[0].isdigit() else 9999, x[0]),
                        )
                    else:
                        sorted_hist = sorted(
                            state["picked_history"].items(),
                            key=lambda x: (-x[1], int(x[0]) if x[0].isdigit() else 9999, x[0]),
                        )
                    badges_html = "".join(
                        f'<div style="display:inline-flex; align-items:center; gap:8px; background:#f1f5f9; border:2px solid #cbd5e1; border-radius:14px; padding:8px 14px; margin:4px 6px 4px 0;">'
                        f'<span style="font-size:1.35rem; font-weight:900; color:#0f172a;">{num}</span>'
                        f'<span style="background:#e0e7ff; color:#3730a3; font-size:0.85rem; font-weight:800; padding:3px 9px; border-radius:999px;">{cnt}次</span>'
                        f'</div>'
                        for num, cnt in sorted_hist
                    )
                    st.markdown(
                        f'<div style="display:flex; flex-wrap:wrap; align-items:center; padding-top:6px;">{badges_html}</div>',
                        unsafe_allow_html=True,
                    )

        live_admin_history_card()

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
                last_winners = list(state.get("last_winners", []))
                saved_num = normalize_seat_num(st.session_state.student_saved_num)
                my_total_score = state.get("scores", {}).get(saved_num, 0) if saved_num else 0
                pts_this_round = state.get("round_points", 1)

                if saved_num:
                    st.markdown(
                        f'<div style="text-align:right; margin-bottom:8px;"><span style="background:#eef2ff; border:1px solid #c7d2fe; color:#3730a3; font-size:0.85rem; font-weight:900; padding:4px 12px; border-radius:999px;">🏆 {saved_num} 號目前累積：{my_total_score} 分</span></div>',
                        unsafe_allow_html=True,
                    )

                if already_submitted and saved_num and saved_num in last_winners:
                    order_num = last_winners.index(saved_num) + 1
                    got_awarded = saved_num in state.get("awarded_winners", [])
                    pts_notice = (
                        f"⭐ 老師已為你加上 {pts_this_round} 分（目前總分 {my_total_score} 分）！"
                        if got_awarded
                        else f"本題答對可得 {pts_this_round} 分，請準備回答問題 🎤"
                    )
                    st.markdown(
                        f"""
                        <div style="background:linear-gradient(135deg, #fde047 0%, #facc15 100%); border:3px solid #eab308; border-radius:20px; padding:24px 16px; text-align:center; color:#0f172a; box-shadow:0 10px 25px rgba(250,204,21,0.35);">
                            <div style="font-size:2.6rem; line-height:1;">🎉</div>
                            <div style="display:inline-block; background:#78350f; color:#fef08a; font-size:1.25rem; font-weight:900; padding:6px 20px; border-radius:999px; margin-top:8px;">
                                第 {order_num} 位發言
                            </div>
                            <div style="font-size:1.45rem; font-weight:900; margin-top:10px;">恭喜 {saved_num} 號中籤！</div>
                            <div style="font-size:0.9rem; font-weight:700; color:#422006; margin-top:6px;">
                                {pts_notice}
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

                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if st.button("🔄 刷新最新結果", use_container_width=True):
                            st.rerun()
                    with btn_c2:
                        # 只要本題仍開放報名且該生還在候選名單中，就允許在抽籤前取消舉手（或改輸入座號）
                        can_cancel = is_open and (saved_num in state["candidates"])
                        if can_cancel:
                            if st.button("🙅 取消舉手 / 改號", use_container_width=True):
                                with state["lock"]:
                                    state["candidates"].pop(saved_num, None)
                                    save_persisted_state(state)
                                st.session_state.submitted_round = 0
                                st.toast(f"已取消 {saved_num} 號的舉手申請")
                                st.rerun()
                        else:
                            st.button("🔒 已鎖定名單", disabled=True, use_container_width=True)
                elif not is_open:
                    st.warning("⏸️ 本題已截止舉手報名，老師正在進行抽籤或討論中，請等待下一題！")
                    if st.button("🔄 檢查是否已開啟下一題", use_container_width=True):
                        st.rerun()
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
                                save_persisted_state(state)
                            st.session_state.student_saved_num = clean_num
                            st.session_state.submitted_round = current_round
                            st.rerun()

        student_live_panel()