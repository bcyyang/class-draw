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
    draw.rectangle([bx - 14, by - 4, bx + 14, by + 4], fill="#0f172a")
    draw.rectangle([bx - 4, by - 14, bx + 4, by + 14], fill="#0f172a")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    return img, b64_str


APP_ICON_IMAGE, APP_ICON_B64 = generate_custom_app_icon()

# ==========================================
# 1. 頁面設定與全域自訂 CSS 樣式
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
    /* 讓高度為 0 的隱藏音效 iframe 脫離版面流（不佔空間也不觸發瀏覽器休眠音效） */
    div[data-testid="stElementContainer"]:has(iframe[height="0"]) {
        position: fixed !important;
        left: -9999px !important;
        top: 0 !important;
        width: 1px !important;
        height: 1px !important;
        opacity: 0 !important;
        pointer-events: none !important;
        margin: 0 !important;
        padding: 0 !important;
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
    /* 聚光燈內部固定高度容器 */
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
    /* 中籤同學金色卡片（與輪轉卡片完全一致的固定尺寸，避免開獎瞬間畫面跳動） */
    .winner-pill {
        background: linear-gradient(180deg, #fde047 0%, #facc15 100%);
        color: #0f172a;
        border: 3px solid #ffffff;
        border-radius: 22px;
        width: 148px;
        height: 174px;
        padding: 12px 10px;
        margin: 6px;
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.28);
        box-sizing: border-box;
        overflow: hidden;
    }
    /* 抽籤滾動跳號卡片（與中籤卡片等寬等高，確保輪轉到開獎無縫銜接） */
    .rolling-pill {
        background: rgba(255, 255, 255, 0.16);
        color: #ffffff;
        border: 3px solid rgba(253, 224, 71, 0.78);
        border-radius: 22px;
        width: 148px;
        height: 174px;
        padding: 12px 10px;
        margin: 6px;
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        justify-content: space-between;
        box-sizing: border-box;
        overflow: hidden;
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
    /* 座次表專屬樣式 */
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
        min-height: 126px;
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

# 注入手機桌面捷徑專屬圖示、自由捲動設定與「防雙指誤觸按鍵音效＋震動監聽器」
components.html(
    f"""
    <script>
    (function() {{
        try {{
            const win = window.parent;
            const doc = win.document;
            let meta = doc.querySelector('meta[name="viewport"]');
            if (!meta) {{
                meta = doc.createElement('meta');
                meta.name = 'viewport';
                doc.head.appendChild(meta);
            }}
            meta.setAttribute('content', 'width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes');

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

            let appTitleMeta = doc.querySelector('meta[name="apple-mobile-web-app-title"]');
            if (!appTitleMeta) {{
                appTitleMeta = doc.createElement('meta');
                appTitleMeta.name = 'apple-mobile-web-app-title';
                doc.head.appendChild(appTitleMeta);
            }}
            appTitleMeta.content = "課堂搶答記分";

            // 1. 在外層主視窗建立全域共用的 Web Audio 引擎，並在使用者首次觸碰/點擊畫面時永久解鎖
            if (!win.__classDrawAudioEngine) {{
                const AudioCtx = win.AudioContext || win.webkitAudioContext;
                const sharedCtx = AudioCtx ? new AudioCtx() : null;

                const unlockAudio = () => {{
                    if (sharedCtx && sharedCtx.state === 'suspended') {{
                        sharedCtx.resume().catch(() => {{}});
                    }}
                }};
                doc.addEventListener('pointerdown', unlockAudio, true);
                doc.addEventListener('keydown', unlockAudio, true);

                win.__classDrawAudioEngine = {{
                    play: function(kind) {{
                        if (!sharedCtx) return;
                        if (sharedCtx.state === 'suspended') {{
                            sharedCtx.resume().catch(() => {{}});
                        }}
                        const now = sharedCtx.currentTime;
                        if (kind === 'rolling') {{
                            for (let i = 0; i < 14; i++) {{
                                const osc = sharedCtx.createOscillator();
                                const gain = sharedCtx.createGain();
                                osc.type = 'sine';
                                osc.frequency.setValueAtTime(420 + i * 28, now + i * 0.085);
                                gain.gain.setValueAtTime(0.14, now + i * 0.085);
                                gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.085 + 0.06);
                                osc.connect(gain);
                                gain.connect(sharedCtx.destination);
                                osc.start(now + i * 0.085);
                                osc.stop(now + i * 0.085 + 0.06);
                            }}
                        }} else if (kind === 'fanfare') {{
                            const notes = [523.25, 659.25, 783.99, 1046.50];
                            notes.forEach((freq, idx) => {{
                                const osc = sharedCtx.createOscillator();
                                const gain = sharedCtx.createGain();
                                osc.type = 'triangle';
                                osc.frequency.setValueAtTime(freq, now + idx * 0.09);
                                gain.gain.setValueAtTime(0.22, now + idx * 0.09);
                                gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.09 + 0.28);
                                osc.connect(gain);
                                gain.connect(sharedCtx.destination);
                                osc.start(now + idx * 0.09);
                                osc.stop(now + idx * 0.09 + 0.28);
                            }});
                        }} else if (kind === 'add' || kind === 'sub') {{
                            const freq = (kind === 'sub') ? 520 : 1000;
                            const osc = sharedCtx.createOscillator();
                            const gain = sharedCtx.createGain();
                            osc.type = 'sine';
                            osc.frequency.setValueAtTime(freq, now);
                            gain.gain.setValueAtTime(0.001, now);
                            gain.gain.linearRampToValueAtTime(0.35, now + 0.008);
                            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.075);
                            osc.connect(gain);
                            gain.connect(sharedCtx.destination);
                            osc.start(now);
                            osc.stop(now + 0.08);
                        }}
                    }}
                }};
            }}

            // 2. 專屬懸停提示 + 連點原地即時累加浮動氣泡 (+1 -> +2 -> +3)
            if (!win.__seatingComboBubbleBoundV2) {{
                win.__seatingComboBubbleBoundV2 = true;

                // 注入浮動計數泡泡樣式
                if (!doc.getElementById('seating-combo-style')) {{
                    const stEl = doc.createElement('style');
                    stEl.id = 'seating-combo-style';
                    stEl.textContent = `
                        #seating-live-combo-pill {{
                            position: fixed;
                            z-index: 2147483647;
                            pointer-events: none;
                            transform: translate(-50%, -100%) scale(0.92);
                            background: linear-gradient(135deg, #facc15 0%, #f59e0b 100%);
                            color: #0f172a;
                            border: 2.5px solid #ffffff;
                            border-radius: 999px;
                            padding: 7px 18px;
                            font-size: 1.12rem;
                            font-weight: 900;
                            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.35);
                            white-space: nowrap;
                            opacity: 0;
                            transition: opacity 0.16s ease, transform 0.14s cubic-bezier(0.22, 1, 0.36, 1);
                        }}
                        #seating-live-combo-pill.sub-mode {{
                            background: linear-gradient(135deg, #334155 0%, #0f172a 100%);
                            color: #ffffff;
                        }}
                        #seating-live-combo-pill.visible {{
                            opacity: 1;
                            transform: translate(-50%, -100%) scale(1.08);
                        }}
                    `;
                    doc.head.appendChild(stEl);
                }}

                const getOrCreateEl = (id) => {{
                    let el = doc.getElementById(id);
                    if (!el) {{
                        el = doc.createElement('div');
                        el.id = id;
                        doc.body.appendChild(el);
                    }}
                    return el;
                }};

                const comboPill = getOrCreateEl('seating-live-combo-pill');

                let comboStudent = '';
                let comboCount = 0;
                let comboHideTimer = null;

                // 計算元素相對於最外層視窗 (win) 的真實螢幕座標（支援嵌套 iframe）
                const getScreenRectInTopWin = (el) => {{
                    let rect = el.getBoundingClientRect();
                    let curWin = el.ownerDocument.defaultView;
                    while (curWin && curWin !== win && curWin.frameElement) {{
                        const fRect = curWin.frameElement.getBoundingClientRect();
                        rect = {{
                            left: rect.left + fRect.left,
                            top: rect.top + fRect.top,
                            width: rect.width,
                            height: rect.height
                        }};
                        curWin = curWin.parent;
                    }}
                    return rect;
                }};

                // 直接從按鈕所屬的座位卡片擷取「座號 + 姓名」，完全不依賴 help/title 屬性
                const inspectSeatingBtn = (btn) => {{
                    if (!btn) return null;
                    const txt = (btn.innerText || btn.textContent || '').trim();
                    if (!txt.includes('➕') && !txt.includes('➖')) return null;

                    if (btn.hasAttribute('title')) btn.removeAttribute('title');

                    let studentLabel = '';
                    let cur = btn.parentElement;
                    for (let i = 0; i < 10 && cur; i++) {{
                        const card = cur.querySelector('.seat-card-box, .seat-card-empty');
                        if (card) {{
                            const lines = (card.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
                            const seatLine = lines.find(l => /^\\d{{2}}$/.test(l)) || '';
                            const nameLine = lines.find(l => l !== seatLine && !l.startsWith('今日') && !l.includes('空位') && l.length <= 8 && !/[甲乙丙丁系科班組]/.test(l)) || '';
                            studentLabel = `${{seatLine}} ${{nameLine}}`.trim();
                            break;
                        }}
                        cur = cur.parentElement;
                    }}
                    if (!studentLabel) studentLabel = '同學';
                    const step = txt.includes('➕') ? 1 : -1;
                    return {{ studentLabel, step }};
                }};

                const triggerLiveComboBubble = (btn, info) => {{
                    if (comboStudent === info.studentLabel && comboPill.classList.contains('visible')) {{
                        comboCount += info.step;
                    }} else {{
                        comboStudent = info.studentLabel;
                        comboCount = info.step;
                    }}

                    const rect = getScreenRectInTopWin(btn);
                    const signText = comboCount > 0 ? `+${{comboCount}} 分` : `${{comboCount}} 分`;
                    comboPill.textContent = `${{comboStudent}}  ${{signText}}`;
                    comboPill.classList.toggle('sub-mode', comboCount < 0);
                    comboPill.style.left = (rect.left + rect.width / 2) + 'px';
                    comboPill.style.top = (Math.max(54, rect.top - 10)) + 'px';

                    comboPill.classList.remove('visible');
                    void comboPill.offsetWidth;
                    comboPill.classList.add('visible');

                    if (comboHideTimer) win.clearTimeout(comboHideTimer);
                    comboHideTimer = win.setTimeout(() => {{
                        comboPill.classList.remove('visible');
                        comboStudent = '';
                        comboCount = 0;
                    }}, 1800);
                }};

                const attachComboToDoc = (targetDoc) => {{
                    if (!targetDoc || targetDoc.__seatingComboAttachedV2) return;
                    targetDoc.__seatingComboAttachedV2 = true;

                    targetDoc.addEventListener('pointerdown', (e) => {{
                        if (e.isPrimary === false) return;
                        const btn = e.target && e.target.closest ? e.target.closest('button') : null;
                        if (!btn || btn.disabled) return;
                        const info = inspectSeatingBtn(btn);
                        if (info) {{
                            triggerLiveComboBubble(btn, info);
                        }}
                    }}, true);
                }};

                attachComboToDoc(doc);
                doc.querySelectorAll('iframe').forEach((fr) => {{
                    try {{ attachComboToDoc(fr.contentDocument); }} catch (e) {{}}
                }});

                // 持續監聽動態新增的 iframe，確保局部刷新後依然有效
                const obs = new MutationObserver(() => {{
                    doc.querySelectorAll('iframe').forEach((fr) => {{
                        try {{ attachComboToDoc(fr.contentDocument); }} catch (e) {{}}
                    }});
                }});
                obs.observe(doc.body, {{ childList: true, subtree: true }});
            }}
        }} catch (e) {{}}
    }})();
    </script>
    """,
    height=0,
    width=0,
)

# ==========================================
# 2. 跨連線持久化共用狀態與輔助函式
# ==========================================
DATA_FILE = "class_draw_state.json"
DEFAULT_ROSTERS_DIR = "default_rosters"
DEFAULT_ROSTERS_JSON = "default_rosters.json"
DEFAULT_PIN = "1234"


def create_empty_rosters():
    return {
        "slot_1": {"custom_name": "", "date_columns": [], "students": {}},
        "slot_2": {"custom_name": "", "date_columns": [], "students": {}},
        "slot_3": {"custom_name": "", "date_columns": [], "students": {}},
    }


def load_default_rosters_from_github():
    """從 GitHub 倉庫預存的 default_rosters.json 或 default_rosters/*.csv 自動載入預設三班名單"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    result = {}

    # 1. 優先讀取 default_rosters.json（若倉庫有存放 JSON 預設名單）
    json_path = os.path.join(base_dir, DEFAULT_ROSTERS_JSON)
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
            if isinstance(raw_json, dict):
                for sk in ("slot_1", "slot_2", "slot_3"):
                    if sk in raw_json and isinstance(raw_json[sk], dict) and raw_json[sk].get("students"):
                        result[sk] = {
                            "custom_name": raw_json[sk].get("custom_name", ""),
                            "date_columns": list(raw_json[sk].get("date_columns", [])),
                            "students": raw_json[sk]["students"],
                        }
                if result:
                    return result
        except Exception:
            pass

    # 2. 搜尋 default_rosters/ 資料夾或倉庫根目錄下的預存 CSV 名單
    search_dirs = [os.path.join(base_dir, DEFAULT_ROSTERS_DIR), base_dir]
    candidate_csvs = []
    for d in search_dirs:
        if os.path.isdir(d):
            for fname in sorted(os.listdir(d)):
                if fname.lower().endswith(".csv") and "範本" not in fname and "sample" not in fname.lower():
                    candidate_csvs.append(os.path.join(d, fname))
        if candidate_csvs:
            break

    if candidate_csvs:
        slot_order = ["slot_1", "slot_2", "slot_3"]
        # 若檔名有明確標示 slot_1 / 1 / 班級1 等，優先對號入座
        unassigned = []
        for fpath in candidate_csvs:
            bname = os.path.basename(fpath)
            matched_slot = None
            for idx, sk in enumerate(slot_order, start=1):
                if f"slot_{idx}" in bname.lower() or f"roster_{idx}" in bname.lower() or f"班級{idx}" in bname:
                    matched_slot = sk
                    break
            if matched_slot and matched_slot not in result:
                try:
                    with open(fpath, "rb") as f:
                        stus, d_cols = parse_roster_csv_bytes(f.read())
                    c_name = os.path.splitext(bname)[0]
                    for prefix in ("slot_1_", "slot_2_", "slot_3_", "roster_1_", "roster_2_", "roster_3_"):
                        if c_name.lower().startswith(prefix):
                            c_name = c_name[len(prefix):]
                    result[matched_slot] = {"custom_name": c_name, "date_columns": d_cols, "students": stus}
                except Exception:
                    pass
            else:
                unassigned.append(fpath)

        for fpath in unassigned:
            avail_slots = [sk for sk in slot_order if sk not in result]
            if not avail_slots:
                break
            sk = avail_slots[0]
            try:
                with open(fpath, "rb") as f:
                    stus, d_cols = parse_roster_csv_bytes(f.read())
                c_name = os.path.splitext(os.path.basename(fpath))[0]
                result[sk] = {"custom_name": c_name, "date_columns": d_cols, "students": stus}
            except Exception:
                pass

    return result


def load_persisted_state():
    default_data = {
        "course_title": "115學年度 課堂即時互動搶答",
        "round_id": 1,
        "is_open": True,
        "candidates": {},
        "picked_history": {},
        "scores": {},
        "round_points": 1,
        "auto_award": True,
        "awarded_winners": [],
        "last_winners": [],
        "student_share_url": "https://class-draw-h29xuk6i83y2w4f4w5dpgn.streamlit.app/",
        "admin_pin": DEFAULT_PIN,
        "active_slot": "slot_1",
        "rosters": create_empty_rosters(),
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                default_data.update(loaded)
        except Exception:
            pass

    if not isinstance(default_data.get("rosters"), dict):
        default_data["rosters"] = create_empty_rosters()

    # 若任何班級名單為空（例如容器重啟清空暫存），自動從 GitHub 預存的 default_rosters 回補
    github_defaults = load_default_rosters_from_github()
    restored_any = False

    for sk in ("slot_1", "slot_2", "slot_3"):
        if sk not in default_data["rosters"] or not isinstance(default_data["rosters"][sk], dict):
            default_data["rosters"][sk] = {"custom_name": "", "date_columns": [], "students": {}}
        default_data["rosters"][sk].setdefault("custom_name", "")
        default_data["rosters"][sk].setdefault("date_columns", [])
        default_data["rosters"][sk].setdefault("students", {})

        if not default_data["rosters"][sk]["students"] and sk in github_defaults:
            default_data["rosters"][sk] = github_defaults[sk]
            restored_any = True

        for seat_k, stu_v in default_data["rosters"][sk]["students"].items():
            if isinstance(stu_v, dict):
                stu_v.setdefault("records", {})
                stu_v.setdefault("semester_total", sum(int(x) for x in stu_v["records"].values()))

    if restored_any:
        save_persisted_state(default_data)
    return default_data


def save_persisted_state(state_obj):
    try:
        payload = {
            "course_title": state_obj["course_title"],
            "round_id": state_obj["round_id"],
            "is_open": state_obj["is_open"],
            "candidates": state_obj["candidates"],
            "picked_history": state_obj["picked_history"],
            "scores": state_obj["scores"],
            "round_points": state_obj["round_points"],
            "auto_award": state_obj["auto_award"],
            "awarded_winners": state_obj["awarded_winners"],
            "last_winners": state_obj["last_winners"],
            "student_share_url": state_obj["student_share_url"],
            "admin_pin": state_obj.get("admin_pin", DEFAULT_PIN),
            "active_slot": state_obj.get("active_slot", "slot_1"),
            "rosters": state_obj.get("rosters", create_empty_rosters()),
        }
        tmp_file = DATA_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, DATA_FILE)
        state_obj["_last_disk_mtime"] = os.path.getmtime(DATA_FILE)
    except Exception:
        pass


def sync_state_from_disk_if_newer(state_obj):
    if not os.path.exists(DATA_FILE):
        return
    try:
        mtime = os.path.getmtime(DATA_FILE)
        if mtime > state_obj.get("_last_disk_mtime", 0):
            with state_obj["lock"]:
                loaded = load_persisted_state()
                for k, v in loaded.items():
                    state_obj[k] = v
                state_obj["_last_disk_mtime"] = mtime
    except Exception:
        pass


@st.cache_resource
def get_classroom_state():
    data = load_persisted_state()
    data["lock"] = threading.Lock()
    data["_last_disk_mtime"] = os.path.getmtime(DATA_FILE) if os.path.exists(DATA_FILE) else 0
    return data


state = get_classroom_state()
sync_state_from_disk_if_newer(state)


def normalize_seat_num(raw_val: str) -> str:
    if not raw_val:
        return ""
    cleaned = "".join(ch for ch in str(raw_val).strip() if ch.isalnum()).upper()
    if cleaned.isdigit():
        num_int = int(cleaned)
        if num_int <= 0:
            return ""
        return f"{num_int:02d}"
    return cleaned


def get_active_slot_obj(state_obj) -> dict:
    active_key = state_obj.get("active_slot", "slot_1")
    rosters = state_obj.get("rosters", {})
    if active_key not in rosters:
        active_key = "slot_1"
    return rosters.get(active_key, {"custom_name": "", "date_columns": [], "students": {}})


def get_active_roster(state_obj) -> dict:
    return get_active_slot_obj(state_obj).get("students", {})


def get_slot_display_title(state_obj, slot_key: str) -> str:
    idx_map = {"slot_1": "班級 1", "slot_2": "班級 2", "slot_3": "班級 3"}
    base_label = idx_map.get(slot_key, "班級")
    slot_obj = state_obj.get("rosters", {}).get(slot_key, {})
    custom = slot_obj.get("custom_name", "").strip()
    count = len(slot_obj.get("students", {}))
    if custom:
        return f"{base_label}：{custom}（{count}人）"
    return f"{base_label}（{count}人）" if count > 0 else f"{base_label}（未匯入）"


def parse_roster_csv_bytes(file_bytes: bytes):
    """解析班級名單 CSV（同時支援基本 3 欄名單，以及匯入先前下載的「多週累計成績總表」）"""
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("無法辨識 CSV 編碼，請使用 UTF-8 或 Excel 預設 CSV 格式儲存。")

    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError("CSV 檔案內容為空！")

    header = [c.strip() for c in rows[0]]
    col_class, col_seat, col_name = 0, 1, 2
    has_header = False
    for i, h in enumerate(header):
        if "班" in h:
            col_class = i
            has_header = True
        elif "座" in h or "號" in h:
            col_seat = i
            has_header = True
        elif "姓" in h or "名" in h:
            col_name = i
            has_header = True

    date_col_indices = []
    if has_header:
        skip_keywords = ("班", "座", "號", "姓", "名", "總", "合計", "累計")
        for i, h in enumerate(header):
            if i not in (col_class, col_seat, col_name) and h and not any(k in h for k in skip_keywords):
                date_col_indices.append((i, h))

    imported_dates = [h for _, h in date_col_indices]
    start_row = 1 if has_header else 0
    roster = {}
    for r in rows[start_row:]:
        if len(r) <= max(col_class, col_seat, col_name):
            continue
        seat_raw = r[col_seat].strip()
        seat_norm = normalize_seat_num(seat_raw)
        if not seat_norm:
            continue
        cls_val = r[col_class].strip()
        name_val = r[col_name].strip()
        if not cls_val and not name_val:
            continue

        records = {}
        for idx_c, d_label in date_col_indices:
            raw_sc = r[idx_c].strip() if idx_c < len(r) else ""
            try:
                records[d_label] = int(float(raw_sc)) if raw_sc != "" else 0
            except ValueError:
                records[d_label] = 0

        sem_total = sum(records.values())
        roster[seat_norm] = {
            "class_name": cls_val,
            "name": name_val,
            "records": records,
            "semester_total": sem_total,
        }

    if not roster:
        raise ValueError("未讀取到有效學生資料，請確認 CSV 包含「班級、座號、姓名」欄位。")
    return roster, imported_dates


def settle_today_scores_to_roster(date_label: str, reset_today: bool = False):
    """將今日暫存分數寫入目前使用中班級的累計總表指定日期欄位"""
    clean_date = str(date_label or "").strip()
    if not clean_date:
        clean_date = datetime.now().strftime("%Y/%m/%d")

    with state["lock"]:
        cur_slot = state.get("active_slot", "slot_1")
        slot_obj = state["rosters"].get(cur_slot)
        if not slot_obj or not slot_obj.get("students"):
            return False, "目前班級尚未匯入名單，請先匯入名單再結算！"

        students = slot_obj["students"]
        date_cols = slot_obj.setdefault("date_columns", [])
        if clean_date not in date_cols:
            date_cols.append(clean_date)

        today_scores = state.get("scores", {})
        all_seats = set(students.keys()) | {s for s, v in today_scores.items() if int(v) > 0}
        scored_count = 0

        for seat in all_seats:
            sc = int(today_scores.get(seat, 0))
            if seat not in students:
                students[seat] = {
                    "class_name": "",
                    "name": f"未建檔({seat}號)",
                    "records": {},
                    "semester_total": 0,
                }
            stu = students[seat]
            stu.setdefault("records", {})
            stu["records"][clean_date] = sc
            stu["semester_total"] = sum(int(v) for v in stu["records"].values())
            if sc > 0:
                scored_count += 1

        if reset_today:
            state["scores"] = {}
            state["awarded_winners"] = []

        save_persisted_state(state)

    if reset_today:
        st.session_state.seating_undo_stack = []
    return True, f"✅ 已將 {scored_count} 位有得分同學寫入「{clean_date}」並更新學期總分（今日分數已保留）！"


def build_semester_gradebook_csv(slot_obj: dict, include_today_preview: bool = False, today_scores: dict = None) -> bytes:
    """產生該班級完整多週累計成績總表 CSV（完整保留 01~最高座號所有空位行列，方便直接複製貼上對齊成績表）"""
    students = slot_obj.get("students", {})
    date_cols = list(slot_obj.get("date_columns", []))
    today_map = today_scores or {}

    has_today = include_today_preview and any(int(v) > 0 for v in today_map.values())
    preview_col_name = f"今日暫存({datetime.now().strftime('%m/%d')})"

    header = ["班級", "座號", "姓名", "學期總加分"] + date_cols
    if has_today:
        header.append(preview_col_name)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)

    all_seats = set(students.keys()) | ({s for s, v in today_map.items() if int(v) > 0} if has_today else set())
    numeric_seats = [int(s) for s in all_seats if str(s).isdigit()]
    non_numeric_seats = sorted([s for s in all_seats if not str(s).isdigit()])

    max_seat_num = max(numeric_seats) if numeric_seats else 64
    ordered_seats = [f"{i:02d}" for i in range(1, max_seat_num + 1)] + non_numeric_seats

    for seat in ordered_seats:
        stu = students.get(seat)
        if stu:
            recs = stu.get("records", {})
            sem_total = sum(int(recs.get(d, 0)) for d in date_cols)
            row = [
                stu.get("class_name", ""),
                seat,
                stu.get("name", ""),
                sem_total,
            ] + [int(recs.get(d, 0)) for d in date_cols]
            if has_today:
                row.append(int(today_map.get(seat, 0)))
        else:
            t_sc = int(today_map.get(seat, 0)) if has_today else 0
            if t_sc > 0:
                row = ["", seat, "", 0] + [0 for _ in date_cols] + [t_sc]
            else:
                row = ["", seat, "", ""] + ["" for _ in date_cols]
                if has_today:
                    row.append("")
        writer.writerow(row)

    return output.getvalue().encode("utf-8-sig")


# ==========================================
# 3. Session State 初始化與網址模式偵測
# ==========================================
qp_mode = st.query_params.get("mode", "")
qp_auth = st.query_params.get("auth", "")
qp_tab = st.query_params.get("tab", "")

if "view_mode" not in st.session_state:
    st.session_state.view_mode = "admin" if qp_mode == "admin" else "student"
if "admin_unlocked" not in st.session_state:
    st.session_state.admin_unlocked = bool(qp_mode == "admin" and qp_auth == "1")
if "admin_tab" not in st.session_state:
    st.session_state.admin_tab = "seating" if qp_tab == "seating" else "draw"
if "draw_mode" not in st.session_state:
    st.session_state.draw_mode = "weighted"
if "draw_count" not in st.session_state:
    st.session_state.draw_count = 1
if "round_points_input" not in st.session_state:
    st.session_state.round_points_input = int(state.get("round_points", 1))
if "auto_award_input" not in st.session_state:
    st.session_state.auto_award_input = bool(state.get("auto_award", True))
if "scoreboard_sort" not in st.session_state:
    st.session_state.scoreboard_sort = "score"
if "history_sort" not in st.session_state:
    st.session_state.history_sort = "count"
if "sound_enabled" not in st.session_state:
    st.session_state.sound_enabled = True
if "play_fanfare_once" not in st.session_state:
    st.session_state.play_fanfare_once = False
if "confirm_new_class" not in st.session_state:
    st.session_state.confirm_new_class = False
if "student_saved_num" not in st.session_state:
    st.session_state.student_saved_num = ""
if "student_confirmed_seat" not in st.session_state:
    st.session_state.student_confirmed_seat = ""
if "student_pending_confirm_seat" not in st.session_state:
    st.session_state.student_pending_confirm_seat = ""
if "submitted_round" not in st.session_state:
    st.session_state.submitted_round = 0
if "student_last_known_score" not in st.session_state:
    st.session_state.student_last_known_score = None
if "student_score_gain_banner" not in st.session_state:
    st.session_state.student_score_gain_banner = None
if "student_url_input" not in st.session_state:
    st.session_state.student_url_input = state["student_share_url"]
if "seating_undo_stack" not in st.session_state:
    st.session_state.seating_undo_stack = []
if "uploader_reset_ids" not in st.session_state:
    st.session_state.uploader_reset_ids = {"slot_1": 0, "slot_2": 0, "slot_3": 0}
if "settle_date_label" not in st.session_state:
    st.session_state.settle_date_label = datetime.now().strftime("%Y/%m/%d")


# ==========================================
# 4. 核心抽籤、音效、CSV 匯出與座次加減分函式
# ==========================================
def sync_round_points_from_widget():
    new_pts = int(st.session_state.round_points_input)
    with state["lock"]:
        state["round_points"] = new_pts
        save_persisted_state(state)


def clear_all_scoreboard_records():
    with state["lock"]:
        state["scores"] = {}
        state["awarded_winners"] = []
        save_persisted_state(state)
    st.session_state["confirm_clear_scores_chk"] = False
    st.session_state["confirm_reset_today_scores_chk"] = False
    st.session_state["scores_cleared_toast"] = True


def open_new_class_confirm():
    st.session_state.confirm_new_class = True


def close_new_class_confirm():
    st.session_state.confirm_new_class = False


def reset_entire_classroom():
    """開啟新課堂：重置今日搶答題次與今日暫存分數，保留三班名單與歷史累計總表"""
    with state["lock"]:
        state["round_id"] = 1
        state["is_open"] = True
        state["candidates"] = {}
        state["picked_history"] = {}
        state["scores"] = {}
        state["last_winners"] = []
        state["awarded_winners"] = []
        save_persisted_state(state)
    st.session_state.confirm_new_class = False
    st.session_state.seating_undo_stack = []
    st.session_state["new_class_toast"] = True


def switch_active_class_slot(slot_key: str):
    if slot_key not in ("slot_1", "slot_2", "slot_3"):
        return
    with state["lock"]:
        state["active_slot"] = slot_key
        save_persisted_state(state)
    st.session_state.seating_undo_stack = []
    st.session_state["class_switched_toast"] = f"🔄 已切換至「{get_slot_display_title(state, slot_key)}」"


def save_slot_custom_name(slot_key: str):
    val = st.session_state.get(f"custom_name_input_{slot_key}", "").strip()
    with state["lock"]:
        if slot_key in state["rosters"]:
            state["rosters"][slot_key]["custom_name"] = val
            save_persisted_state(state)


def pick_weighted_candidates(candidates_dict, history_dict, count=1, weighted=True):
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


def generate_qr_base64(url: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e1b4b", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def play_sound_effect(kind="rolling", enabled=True):
    if not enabled:
        return
    js_code = f"""
    <script>
    (function() {{
        try {{
            if (window.parent && window.parent.__classDrawAudioEngine) {{
                window.parent.__classDrawAudioEngine.play("{kind}");
            }}
        }} catch (e) {{}}
    }})();
    </script>
    """
    components.html(js_code, height=0, width=0)


def build_scores_csv(scores_dict, history_dict, sort_mode="seat", roster_dict=None, fallback_date_col=""):
    """產生單堂課即時成績 CSV 資料（若今日分數已歸零但該日期剛結算過，自動從該日期欄位帶出分數）"""
    roster = roster_dict or {}
    all_seats = set(scores_dict.keys()) | set(history_dict.keys()) | set(roster.keys())
    has_live_scores = any(int(v) > 0 for v in scores_dict.values())

    items = []
    for seat in all_seats:
        sc = int(scores_dict.get(seat, 0))
        info = roster.get(seat, {})
        if not has_live_scores and fallback_date_col:
            sc = int(info.get("records", {}).get(fallback_date_col, 0))
        if sc <= 0:
            continue
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
    writer.writerow(["座號", "班級", "姓名", "今日得分", "發言次數"])

    plain_lines = ["座號\t班級\t姓名\t今日得分\t發言次數"]
    for cls_name, seat, stu_name, sc, cnt in items:
        writer.writerow([seat, cls_name, stu_name, sc, cnt])
        plain_lines.append(f"{seat}\t{cls_name}\t{stu_name}\t{sc}分\t({cnt}次)")

    if not items:
        plain_lines.append("（今日目前尚無任何得分紀錄）")

    csv_bytes = output.getvalue().encode("utf-8-sig")
    return csv_bytes, "\n".join(plain_lines)


def generate_sample_roster_csv() -> bytes:
    """產生班級名單 CSV 範本"""
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
    """點擊座次表時直接加減該生今日暫存分數"""
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

    now_ts = time.time()
    tracker = st.session_state.get("seating_combo_tracker", {"seat": "", "delta": 0, "ts": 0.0})
    if record_undo and actual_delta != 0:
        if tracker.get("seat") == seat and (now_ts - tracker.get("ts", 0.0) <= 4.0):
            combo_delta = tracker.get("delta", 0) + actual_delta
        else:
            combo_delta = actual_delta
        st.session_state.seating_combo_tracker = {
            "seat": seat,
            "delta": combo_delta,
            "ts": now_ts,
        }
    else:
        combo_delta = actual_delta

    if actual_delta > 0:
        st.session_state.seating_feedback_trigger = ("add", time.time())
    elif actual_delta < 0:
        st.session_state.seating_feedback_trigger = ("sub", time.time())
    else:
        st.session_state["seating_toast_msg"] = f"ℹ️ {display_who} 今日目前已是 0 分"
        st.session_state.seating_feedback_trigger = ("sub", time.time())


def play_seating_click_feedback(kind="add"):
    """播放最單純乾淨的純弦波單音（加分 1000Hz / 減分 520Hz）並觸發手機短震動回饋"""
    vib_ms = 60 if kind == "sub" else 45
    js_code = f"""
    <script>
    (function() {{
        try {{
            if (navigator && navigator.vibrate) {{
                navigator.vibrate({vib_ms});
            }}
        }} catch (e) {{}}
        try {{
            if (window.parent && window.parent.__classDrawAudioEngine) {{
                window.parent.__classDrawAudioEngine.play("{kind}");
            }}
        }} catch (e) {{}}
    }})();
    </script>
    """
    components.html(js_code, height=0, width=0)


def undo_last_seating_click():
    """復原上一筆在座次表的點擊加減分"""
    if not st.session_state.seating_undo_stack:
        return
    seat, last_delta = st.session_state.seating_undo_stack.pop()
    adjust_seat_score(seat, -last_delta, record_undo=False)
    stu_name = get_active_roster(state).get(seat, {}).get("name", "")
    st.session_state["seating_toast_msg"] = f"↩️ 已復原 {seat}號 {stu_name} 的上一筆變動（今日 {state['scores'].get(seat, 0)} 分）"


def render_spotlight_html(winners, rolling=False, total_pool=0, round_points=1, awarded_list=None):
    awarded_set = set(awarded_list or [])
    roster = get_active_roster(state)
    if rolling:
        pills_list = []
        for idx, num in enumerate(winners):
            pills_list.append(
                f'<div class="rolling-pill">'
                f'<span style="background:rgba(253,224,71,0.22); color:#fde047; font-size:0.95rem; font-weight:900; padding:3px 16px; border-radius:999px; letter-spacing:0.06em; line-height:1.3;">第 {idx + 1} 位</span>'
                f'<span style="font-size:3.1rem; font-weight:900; line-height:1.05; color:#ffffff;">{num}</span>'
                f'<div style="height:38px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px;">'
                f'<span style="font-size:0.95rem; font-weight:800; color:#e2e8f0; line-height:1.2;">抽籤中...</span>'
                f'<span style="background:rgba(255,255,255,0.14); color:#fde047; font-size:0.72rem; font-weight:800; padding:1px 10px; border-radius:999px; line-height:1.3;">配分 {round_points} 分</span>'
                f'</div>'
                f'</div>'
            )
        pills = "".join(pills_list)
        inner = (
            f'<div style="color:#fde047; font-size:0.98rem; font-weight:800; letter-spacing:0.06em; margin-bottom:10px; line-height:1.4;">'
            f'🎰 正在從 {total_pool} 位舉手同學中抽出 {len(winners)} 位...</div>'
            f'<div style="display:flex; flex-wrap:wrap; justify-content:center; align-items:center;">{pills}</div>'
        )
    elif winners:
        pills_list = []
        for idx, num in enumerate(winners):
            stu_name = roster.get(num, {}).get("name", "")
            name_html = (
                f'<span style="font-size:0.95rem; font-weight:900; color:#1e293b; line-height:1.2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:124px;">{stu_name}</span>'
                if stu_name
                else '<span style="font-size:0.85rem; font-weight:700; color:#78350f; line-height:1.2;">中籤同學</span>'
            )
            got_pts = (
                f'<span style="background:#059669; color:#ffffff; font-size:0.72rem; font-weight:900; padding:1px 10px; border-radius:999px; line-height:1.3;">✓ 已加分</span>'
                if num in awarded_set
                else f'<span style="background:rgba(15,23,42,0.12); color:#422006; font-size:0.72rem; font-weight:800; padding:1px 10px; border-radius:999px; line-height:1.3;">待給 {round_points} 分</span>'
            )
            pills_list.append(
                f'<div class="winner-pill">'
                f'<span style="background:#78350f; color:#fef08a; font-size:0.95rem; font-weight:900; padding:3px 16px; border-radius:999px; letter-spacing:0.06em; line-height:1.3;">第 {idx + 1} 位</span>'
                f'<span style="font-size:3.1rem; font-weight:900; line-height:1.05; color:#0f172a;">{num}</span>'
                f'<div style="height:38px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px;">{name_html}{got_pts}</div>'
                f'</div>'
            )
        pills = "".join(pills_list)
        inner = (
            f'<div style="color:#fde047; font-size:0.98rem; font-weight:800; letter-spacing:0.06em; margin-bottom:10px; line-height:1.4;">'
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
# 5. 頂部精簡視角切換列
# ==========================================
nav_col1, nav_col2, nav_col3 = st.columns([8.2, 0.9, 0.9])
with nav_col1:
    st.markdown(
        '<div style="font-size:0.78rem; color:#64748b; padding-top:4px;">💡 同網址雙模式：預設為學生端；網址加 <code>?mode=admin</code> 即為老師端 · <span style="background:#dcfce7; color:#166534; font-weight:800; padding:1px 8px; border-radius:999px;">v4.0 學期累計總表版</span></div>',
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

    # --- 頂部課程標題與開題控制列 ---
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
            help="重置今日搶答題次與今日暫存分數（保留三班名單與歷史累計總表）",
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

    # --- 雙畫面工作區切換 + 三班名單一鍵切換列 ---
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
                st.warning("⚠️ 確定要**開啟新課堂**嗎？這將會把**題次歸 1、今日暫存分數與舉手名單清空**（已結算寫入的「學期累計總表」會完整保留）！")
            with warn_c2:
                st.button(
                    "✅ 確定重置今日紀錄",
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

    if st.session_state.pop("scores_cleared_toast", False):
        st.toast("🗑️ 已清空今日暫存記分板紀錄！")

    if st.session_state.pop("new_class_toast", False):
        st.toast("🏫 已開啟新課堂，今日暫存紀錄已重置（歷史累計總表已保留）！")

    class_switched_toast = st.session_state.pop("class_switched_toast", None)
    if class_switched_toast:
        st.toast(class_switched_toast)

    seating_toast_msg = st.session_state.pop("seating_toast_msg", None)
    if seating_toast_msg:
        st.toast(seating_toast_msg)

    seating_fb = st.session_state.pop("seating_feedback_trigger", None)
    if seating_fb:
        play_seating_click_feedback(seating_fb[0])

    # ========================================================
    # 分頁 B：🗺️ 全班座次表互動記分 + 學期累計總表結算
    # ========================================================
    if st.session_state.admin_tab == "seating":
        slot_obj = get_active_slot_obj(state)
        roster = slot_obj["students"]
        cur_slot_key = state.get("active_slot", "slot_1")
        date_cols = slot_obj.get("date_columns", [])

        # 1. 上方精簡操作列（僅保留點擊說明與復原上一筆）+ 收合式管理面板
        with st.container(border=True):
            ctrl_c1, ctrl_c2 = st.columns([7.8, 2.2])
            with ctrl_c1:
                st.markdown(
                    '<div style="padding-top:6px; font-size:0.94rem; font-weight:700; color:#1e293b;">'
                    '👆 點擊座位下方 <span style="color:#4f46e5;">➕ 加 1 分</span> / <span style="color:#64748b;">➖ 減 1 分</span></div>',
                    unsafe_allow_html=True,
                )
            with ctrl_c2:
                undo_len = len(st.session_state.seating_undo_stack)
                st.button(
                    f"↩️ 復原 ({undo_len})" if undo_len > 0 else "↩️ 復原上一筆",
                    disabled=(undo_len == 0),
                    use_container_width=True,
                    key="seating_undo_btn",
                    on_click=undo_last_seating_click,
                )

            # 展開區：管理三個班級的 CSV 名單 + 結算今日寫入總表 + 下載成績總表
            with st.expander("📂 管理三個班級的 CSV 名單、結算今日成績與下載總表", expanded=False):
                info_c1, info_c2, info_c3 = st.columns([5.3, 2.4, 2.3])
                with info_c1:
                    st.caption("💡 支援兩種 CSV 匯入：① 學期初的「班級、座號、姓名」三欄名單；② 上週下載的「學期累計成績總表 (.csv)」，匯入後會自動還原過去所有日期欄位並繼續往右累加！")
                with info_c2:
                    if st.button("🔄 載入 GitHub 預設名單", use_container_width=True, key="reload_github_default_rosters_btn"):
                        gh_rosters = load_default_rosters_from_github()
                        if gh_rosters:
                            with state["lock"]:
                                for sk_g, val_g in gh_rosters.items():
                                    state["rosters"][sk_g] = val_g
                                save_persisted_state(state)
                            st.toast(f"✅ 已從 GitHub 重新載入 {len(gh_rosters)} 個班級的預設名單！")
                            st.rerun()
                        else:
                            st.warning("未在倉庫中找到 default_rosters 資料夾或預設 CSV 檔案。")
                with info_c3:
                    st.download_button(
                        label="📄 下載空白名單範本",
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
                            s_dates_cnt = len(state["rosters"][s_key].get("date_columns", []))
                            if is_active_slot:
                                st.markdown(f"**🟢 {slot_title}**（使用中 · 已記 {s_dates_cnt} 次）")
                            else:
                                st.markdown(f"**⚪ {slot_title}**（已記 {s_dates_cnt} 次）")

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
                                        new_roster, imported_dates = parse_roster_csv_bytes(up_file.getvalue())
                                        with state["lock"]:
                                            state["rosters"][s_key]["students"] = new_roster
                                            state["rosters"][s_key]["date_columns"] = imported_dates
                                            state["active_slot"] = s_key
                                            save_persisted_state(state)
                                        st.session_state.uploader_reset_ids[s_key] = st.session_state.uploader_reset_ids.get(s_key, 0) + 1
                                        extra_msg = f"（含 {len(imported_dates)} 次歷史日期成績）" if imported_dates else ""
                                        st.toast(f"🎉 已匯入「{get_slot_display_title(state, s_key)}」{extra_msg}！")
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
                                        state["rosters"][s_key]["date_columns"] = []
                                        save_persisted_state(state)
                                    st.toast(f"已清除班級 {idx + 1} 名單與累計紀錄")

                st.divider()

                # 下方收納：本班歷史堂數、結算今日寫入總表、下載學期累計總表與今日明細
                st.markdown(
                    f'<div style="font-size:0.92rem; font-weight:800; color:#1e293b; margin-bottom:8px;">'
                    f'📊 本班成績結算與下載（已累計 <span style="color:#059669;">{len(date_cols)} 堂課</span> 歷史紀錄）</div>',
                    unsafe_allow_html=True,
                )
                settle_c1, settle_c2, settle_c3, settle_c4 = st.columns([2.2, 2.4, 2.7, 2.7])
                with settle_c1:
                    st.text_input(
                        "結算日期欄位名稱",
                        key="settle_date_label",
                        label_visibility="collapsed",
                        placeholder="如 2026/11/23",
                        help="下課結算時，將今日分數寫入此日期欄位名稱",
                    )
                with settle_c2:
                    if st.button(
                        "💾 結算今日寫入總表",
                        type="primary",
                        use_container_width=True,
                        key="settle_today_btn",
                        help="將今日所有同學得分寫入上方日期欄位並更新學期總分（保留今日得分，不會自動歸零）",
                    ):
                        ok, msg = settle_today_scores_to_roster(st.session_state.settle_date_label, reset_today=False)
                        if ok:
                            st.toast(msg)
                            st.rerun()
                        else:
                            st.warning(msg)
                with settle_c3:
                    semester_csv_bytes = build_semester_gradebook_csv(
                        slot_obj,
                        include_today_preview=False,
                        today_scores=state["scores"],
                    )
                    today_str = datetime.now().strftime("%Y%m%d")
                    slot_short_name = get_slot_display_title(state, cur_slot_key).split("（")[0].replace("：", "_")
                    st.download_button(
                        label="📊 下載學期累計總表 (.csv)",
                        data=semester_csv_bytes,
                        file_name=f"{slot_short_name}_學期累計成績總表_{today_str}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="seating_download_semester_csv_btn",
                    )
                with settle_c4:
                    clean_settle_date = st.session_state.settle_date_label.strip() or datetime.now().strftime("%Y/%m/%d")
                    today_csv_bytes, _ = build_scores_csv(
                        state["scores"],
                        state["picked_history"],
                        sort_mode="seat",
                        roster_dict=roster,
                        fallback_date_col=clean_settle_date,
                    )
                    st.download_button(
                        label="📥 僅下載今日得分明細",
                        data=today_csv_bytes,
                        file_name=f"{slot_short_name}_今日得分_{today_str}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="seating_download_today_csv_btn",
                    )

                rst_c1, rst_c2 = st.columns([6.8, 3.2])
                with rst_c1:
                    confirm_reset_today = st.checkbox(
                        "確認已結算並下載完成，要將今日暫存分數歸零（準備下一堂課）",
                        key="confirm_reset_today_scores_chk",
                    )
                with rst_c2:
                    st.button(
                        "🧹 手動歸零今日分數",
                        disabled=not confirm_reset_today,
                        use_container_width=True,
                        key="manual_reset_today_scores_btn",
                        on_click=clear_all_scoreboard_records,
                    )

                if date_cols:
                    recent_str = "、".join(date_cols[-6:])
                    more_str = f" 等共 {len(date_cols)} 次" if len(date_cols) > 6 else ""
        # 2. 渲染 8 列 × 8 欄座次表（採用局部刷新與低頻輪詢，大幅消除手機/平板連續點擊加減分的 Lag）
        @st.fragment(run_every=6)
        def live_seating_grid():
            sync_state_from_disk_if_newer(state)
            cur_roster = get_active_roster(state)

            toast_msg = st.session_state.pop("seating_toast_msg", None)
            if toast_msg:
                st.toast(toast_msg)

            aisle_header_cols = st.columns([1, 1, 0.14, 1, 1, 0.14, 1, 1, 0.14, 1, 1], gap="small")
            for group_idx, col_pos in enumerate([0, 3, 6, 9]):
                with aisle_header_cols[col_pos]:
                    st.markdown(
                        f'<div style="text-align:center; font-size:0.78rem; font-weight:800; color:#64748b; background:#f1f5f9; border-radius:8px; padding:2px 0; margin-bottom:2px;">第 {group_idx + 1} 排（左）</div>',
                        unsafe_allow_html=True,
                    )
                with aisle_header_cols[col_pos + 1]:
                    st.markdown(
                        f'<div style="text-align:center; font-size:0.78rem; font-weight:800; color:#64748b; background:#f1f5f9; border-radius:8px; padding:2px 0; margin-bottom:2px;">第 {group_idx + 1} 排（右）</div>',
                        unsafe_allow_html=True,
                    )
            for div_pos in (2, 5, 8):
                with aisle_header_cols[div_pos]:
                    if div_pos == 5:
                        st.markdown(
                            '<div style="text-align:center; font-size:0.72rem; font-weight:900; color:#4f46e5; padding-top:2px;">中走道</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            '<div style="text-align:center; font-size:0.72rem; font-weight:900; color:#94a3b8; padding-top:2px;">走道</div>',
                            unsafe_allow_html=True,
                        )

            for row_idx in range(7, -1, -1):
                row_cols = st.columns([1, 1, 0.14, 1, 1, 0.14, 1, 1, 0.14, 1, 1], gap="small")

                for div_pos in (2, 5, 8):
                    with row_cols[div_pos]:
                        if div_pos == 5:
                            st.markdown(
                                '<div style="display:flex; justify-content:center; height:172px;">'
                                '<div style="width:3.5px; height:100%; background:#6366f1; border-radius:2px;"></div>'
                                '</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                '<div style="display:flex; justify-content:center; height:172px;">'
                                '<div style="width:2.5px; height:100%; background:repeating-linear-gradient(to bottom, #94a3b8 0, #94a3b8 7px, transparent 7px, transparent 13px); border-radius:2px;"></div>'
                                '</div>',
                                unsafe_allow_html=True,
                            )

                for col_idx in range(8):
                    target_col_idx = col_idx + (col_idx // 2)
                    seat_int = row_idx * 8 + col_idx + 1
                    seat_str = f"{seat_int:02d}"
                    stu_info = cur_roster.get(seat_str)
                    cur_score = int(state["scores"].get(seat_str, 0))

                    with row_cols[target_col_idx]:
                        if stu_info:
                            cls_label = stu_info.get("class_name", "") or "　"
                            name_label = stu_info.get("name", "") or "未命名"
                            card_cls = "seat-card-box has-score" if cur_score > 0 else "seat-card-box"
                            score_badge_bg = "#d97706" if cur_score > 0 else "#64748b"
                            st.markdown(
                                f'<div class="{card_cls}">'
                                f'<div style="font-size:0.72rem; font-weight:400; color:#475569; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{cls_label}</div>'
                                f'<div style="font-size:1.25rem; font-weight:500; color:#0f172a; line-height:1.12; margin:1px 0;">{seat_str}</div>'
                                f'<div style="font-size:0.96rem; font-weight:500; color:#1e293b; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{name_label}</div>'
                                f'<div style="margin-top:5px;"><span style="background:{score_badge_bg}; color:#ffffff; font-size:0.88rem; font-weight:800; padding:2px 10px; border-radius:999px; display:inline-block;">今日 {cur_score} 分</span></div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                            b_add, b_sub = st.columns([1.3, 1.0], gap="small")
                            with b_add:
                                if st.button(
                                    "➕",
                                    key=f"seat_add_{seat_str}",
                                    use_container_width=True,
                                    type="secondary",
                                ):
                                    adjust_seat_score(seat_str, 1, True)
                                    st.rerun(scope="fragment")
                            with b_sub:
                                if st.button(
                                    "➖",
                                    key=f"seat_sub_{seat_str}",
                                    use_container_width=True,
                                    disabled=(cur_score == 0),
                                ):
                                    adjust_seat_score(seat_str, -1, True)
                                    st.rerun(scope="fragment")
                        else:
                            card_cls = "seat-card-box has-score" if cur_score > 0 else "seat-card-empty"
                            if cur_score > 0:
                                st.markdown(
                                    f'<div class="{card_cls}">'
                                    f'<div style="font-size:0.72rem; font-weight:400; color:#64748b;">空位 / 未建檔</div>'
                                    f'<div style="font-size:1.3rem; font-weight:500; color:#0f172a; line-height:1.15; margin:2px 0;">{seat_str}</div>'
                                    f'<div style="margin-top:6px;"><span style="background:#d97706; color:#ffffff; font-size:0.9rem; font-weight:800; padding:3px 10px; border-radius:999px; display:inline-block;">今日 {cur_score} 分</span></div>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    f'<div class="seat-card-empty"><div style="font-size:1.15rem; font-weight:500; color:#94a3b8;">{seat_str}</div><div>空位</div></div>',
                                    unsafe_allow_html=True,
                                )
                            b_add, b_sub = st.columns([1.3, 1.0], gap="small")
                            with b_add:
                                if st.button(
                                    "➕",
                                    key=f"seat_empty_add_{seat_str}",
                                    use_container_width=True,
                                ):
                                    adjust_seat_score(seat_str, 1, True)
                                    st.rerun(scope="fragment")
                            with b_sub:
                                if st.button(
                                    "➖",
                                    key=f"seat_empty_sub_{seat_str}",
                                    use_container_width=True,
                                    disabled=(cur_score == 0),
                                ):
                                    adjust_seat_score(seat_str, -1, True)
                                    st.rerun(scope="fragment")

        live_seating_grid()
        st.markdown('<div class="podium-banner">講　　　　台</div>', unsafe_allow_html=True)
        st.stop()

    # ========================================================
    # 分頁 A：🎯 搶答抽籤主控台
    # ========================================================
    left_col, right_col = st.columns([8, 4], gap="large")
    rolling_sound_box = st.empty()

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
                                f'<div class="{card_cls}"><div class="candidate-num">{num}</div>{badge_html}<div style="font-size:0.72rem; color:#64748b; margin-top:3px;">今日{pts_tag if pts_tag else " 0分"}</div></div>',
                                unsafe_allow_html=True,
                            )

            return spotlight_placeholder

        spotlight_placeholder = live_admin_left_board()

    with right_col:
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
                    help="依題目難度設定本題答對可得幾分",
                )

            cur_auto_award = bool(state.get("auto_award", True))
            new_auto_award = st.toggle(
                "⚡ 抽中時自動加上本題配分",
                value=cur_auto_award,
            )
            if new_auto_award != cur_auto_award:
                with state["lock"]:
                    state["auto_award"] = new_auto_award
                    save_persisted_state(state)
                st.session_state.auto_award_input = new_auto_award
                st.toast("⚡ 已開啟抽中自動給分" if new_auto_award else "⏸️ 已關閉抽中自動給分（改為手動給分）")
                st.rerun()

            cur_sound_enabled = bool(st.session_state.get("sound_enabled", True))
            new_sound_enabled = st.toggle(
                "🔊 啟用抽籤跳號與中獎音效",
                value=cur_sound_enabled,
            )
            if new_sound_enabled != cur_sound_enabled:
                st.session_state.sound_enabled = new_sound_enabled
                st.toast("🔊 已開啟抽籤音效" if new_sound_enabled else "🔇 已關閉抽籤音效（靜音模式）")
                st.rerun()

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
                    auto_give = bool(state.get("auto_award", True))
                    sound_on = bool(st.session_state.get("sound_enabled", True))

                    with rolling_sound_box:
                        play_sound_effect("rolling", enabled=sound_on)

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

                    st.session_state.play_fanfare_once = sound_on
                    st.rerun()

        @st.fragment(run_every=2)
        def live_admin_scoreboard_card():
            sync_state_from_disk_if_newer(state)
            with st.container(border=True):
                st.markdown("#### 🏆 今日即時記分板")

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

                all_seats = set(state["scores"].keys()) | set(state["picked_history"].keys())
                score_items = [(seat, int(state["scores"].get(seat, 0))) for seat in all_seats if int(state["scores"].get(seat, 0)) > 0]

                if not score_items:
                    st.markdown(
                        '<div style="padding:14px 12px; border-radius:12px; background:#f8fafc; border:1px dashed #cbd5e1; color:#94a3b8; font-size:0.88rem; text-align:center; margin-top:6px;">今日尚無得分紀錄（抽中同學或於座次表加分後將顯示於此）</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    if st.session_state.scoreboard_sort == "score":
                        score_items.sort(key=lambda x: (-x[1], int(x[0]) if x[0].isdigit() else 9999, x[0]))
                    else:
                        score_items.sort(key=lambda x: (int(x[0]) if x[0].isdigit() else 9999, x[0]))

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
                        f'<div style="max-height:280px; overflow-y:auto; padding-right:2px;">{"".join(rows_html)}</div>',
                        unsafe_allow_html=True,
                    )

                    csv_bytes, plain_summary = build_scores_csv(
                        state["scores"],
                        state["picked_history"],
                        sort_mode=st.session_state.scoreboard_sort,
                        roster_dict=get_active_roster(state),
                    )
                    today_str = datetime.now().strftime("%Y%m%d")
                    safe_title = "".join(c for c in state["course_title"] if c.isalnum() or c in ("_", "-")) or "課堂成績"
                    st.download_button(
                        label="📥 下載今日得分明細 (.csv)",
                        data=csv_bytes,
                        file_name=f"{safe_title}_今日得分_{today_str}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        type="primary",
                        key="download_scores_csv_btn",
                    )
                    with st.expander("📋 快速複製文字版成績（貼上 LINE / 試算表）"):
                        st.code(plain_summary, language="text")

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
                                st.toast(f"已調整 {clean_s} 號今日分數（目前 {new_val} 分）")
                                st.rerun()

                    st.divider()
                    confirm_clear_scores = st.checkbox(
                        "確認要清空今日暫存記分板紀錄",
                        key="confirm_clear_scores_chk",
                    )
                    st.button(
                        "🗑️ 清空今日暫存記分板紀錄",
                        disabled=not confirm_clear_scores,
                        use_container_width=True,
                        key="clear_all_scores_btn",
                        on_click=clear_all_scoreboard_records,
                    )

        live_admin_scoreboard_card()

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

        with st.container(border=True):
            st.markdown("#### 📱 學生手機掃碼加入")
            share_url = st.text_input(
                "學生端網址（自動過濾老師端參數，確保掃碼直接進入學生端）",
                value=st.session_state.student_url_input,
            )
            clean_student_url = share_url.strip().split("?")[0]
            if clean_student_url != st.session_state.student_url_input:
                st.session_state.student_url_input = clean_student_url
                with state["lock"]:
                    state["student_share_url"] = clean_student_url
                    save_persisted_state(state)
            if clean_student_url:
                qr_b64 = generate_qr_base64(clean_student_url)
                st.markdown(
                    f'<div style="text-align:center; padding:4px 0;"><img src="data:image/png;base64,{qr_b64}" width="150" style="border-radius:12px; border:1px solid #e2e8f0; padding:6px; background:#fff;"/></div>',
                    unsafe_allow_html=True,
                )
                st.caption(f"🔗 學生端網址：`{clean_student_url}`")

    # 固定在整個頁面最底部（左右兩欄之外）播放中獎音效
    if st.session_state.play_fanfare_once:
        play_sound_effect("fanfare", enabled=st.session_state.sound_enabled)
        st.session_state.play_fanfare_once = False

# ==========================================
# 7. 學生手機端 (STUDENT VIEW - 無密碼直接進入)
# ==========================================
else:
    _, stu_col, _ = st.columns([1, 1.45, 1])
    with stu_col:

        @st.fragment(run_every=2)
        def live_student_panel():
            sync_state_from_disk_if_newer(state)
            cur_round = state["round_id"]
            is_open = state["is_open"]
            roster = get_active_roster(state)

            status_badge = (
                '<div class="status-open">🟢 舉手報名開放中</div>'
                if is_open
                else '<div class="status-closed">🔴 本題已截止報名</div>'
            )
            st.markdown(
                f'<div class="student-header">'
                f'<div style="font-size:0.85rem; opacity:0.85; font-weight:700;">第 {cur_round} 題 · 即時互動搶答</div>'
                f'<div style="font-size:1.55rem; font-weight:900; margin-top:4px;">{state["course_title"]}</div>'
                f'{status_badge}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # 若學生已輸入過座號，頂部顯示個人今日分數與學期總加分看板
            saved_seat = st.session_state.student_saved_num
            if saved_seat:
                today_sc = int(state["scores"].get(saved_seat, 0))
                stu_rec = roster.get(saved_seat, {})
                stu_nm = stu_rec.get("name", "")
                sem_sc = int(stu_rec.get("semester_total", 0))

                prev_sc = st.session_state.student_last_known_score
                if prev_sc is not None and today_sc > prev_sc:
                    st.session_state.student_score_gain_banner = (today_sc - prev_sc, time.time())
                st.session_state.student_last_known_score = today_sc

                gain_info = st.session_state.student_score_gain_banner
                if gain_info and (time.time() - gain_info[1] < 8):
                    st.success(f"🎉 太棒了！老師剛剛為你加上 **+{gain_info[0]} 分**！")

                st.markdown(
                    f'<div style="background:#f8fafc; border:2px solid #c7d2fe; border-radius:16px; padding:12px 16px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">'
                    f'<div><div style="font-size:0.78rem; color:#64748b; font-weight:700;">目前綁定座號</div>'
                    f'<div style="font-size:1.25rem; font-weight:900; color:#1e1b4b;">{saved_seat} 號 {stu_nm}</div></div>'
                    f'<div style="text-align:right;">'
                    f'<div style="background:#4f46e5; color:#ffffff; font-size:0.95rem; font-weight:900; padding:3px 12px; border-radius:999px;">今日 {today_sc} 分</div>'
                    f'<div style="font-size:0.75rem; font-weight:800; color:#059669; margin-top:4px;">學期累計 {sem_sc} 分</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

            with st.container(border=True):
                raw_seat = st.text_input(
                    "請輸入你的座號（例如：05 或 12）",
                    value=st.session_state.student_saved_num,
                    placeholder="輸入座號後點擊舉手搶答",
                    max_chars=6,
                )
                clean_seat = normalize_seat_num(raw_seat)
                if clean_seat != st.session_state.student_saved_num:
                    st.session_state.student_saved_num = clean_seat
                    st.session_state.student_pending_confirm_seat = ""
                    st.session_state.student_last_known_score = int(state["scores"].get(clean_seat, 0)) if clean_seat else None

                already_in_pool = bool(clean_seat and clean_seat in state["candidates"])
                last_winners_list = list(state.get("last_winners", []))
                is_winner_now = bool(clean_seat and clean_seat in last_winners_list)
                is_confirmed_for_seat = bool(clean_seat and st.session_state.student_confirmed_seat == clean_seat)

                if is_winner_now:
                    winner_rank = last_winners_list.index(clean_seat) + 1
                    st.success(f"🎉 恭喜 **{clean_seat} 號**！你是 **第 {winner_rank} 位** 中籤發言同學，請準備回答！")
                elif already_in_pool:
                    st.info(f"🙋 **{clean_seat} 號** 已在「第 {cur_round} 題」舉手名單中，請靜候老師抽籤！")
                elif not is_open:
                    st.warning("⏸️ 本題目前暫停舉手報名，請等待老師開啟下一題。")
                elif clean_seat and not is_confirmed_for_seat and st.session_state.student_pending_confirm_seat == clean_seat:
                    # 首次輸入該座號時的身分確認卡片
                    stu_info = roster.get(clean_seat, {})
                    stu_name = stu_info.get("name", "").strip()
                    stu_cls = stu_info.get("class_name", "").strip()
                    if stu_name:
                        cls_prefix = f"{stu_cls} · " if stu_cls else ""
                        confirm_html = (
                            f'<div style="background:#fffbeb; border:2px solid #f59e0b; border-radius:14px; padding:14px 16px; margin-bottom:10px; text-align:center;">'
                            f'<div style="font-size:0.84rem; font-weight:800; color:#b45309;">🔍 首次使用請確認你的身分</div>'
                            f'<div style="font-size:1.35rem; font-weight:900; color:#0f172a; margin-top:4px;">{cls_prefix}{clean_seat} 號 · {stu_name}</div>'
                            f'<div style="font-size:0.8rem; color:#64748b; margin-top:4px;">確認無誤後，之後舉手將自動送出不再詢問</div>'
                            f'</div>'
                        )
                    else:
                        confirm_html = (
                            f'<div style="background:#fffbeb; border:2px solid #f59e0b; border-radius:14px; padding:14px 16px; margin-bottom:10px; text-align:center;">'
                            f'<div style="font-size:0.84rem; font-weight:800; color:#b45309;">🔍 首次使用請確認你的座號</div>'
                            f'<div style="font-size:1.35rem; font-weight:900; color:#0f172a; margin-top:4px;">座號：{clean_seat} 號（名單未建檔）</div>'
                            f'<div style="font-size:0.8rem; color:#64748b; margin-top:4px;">請確認座號沒有按錯，確認後之後舉手將直接送出</div>'
                            f'</div>'
                        )
                    st.markdown(confirm_html, unsafe_allow_html=True)

                    cfm_c1, cfm_c2 = st.columns(2)
                    with cfm_c1:
                        if st.button("✅ 是，確認是我並送出", type="primary", use_container_width=True, key="stu_confirm_yes_btn"):
                            st.session_state.student_confirmed_seat = clean_seat
                            st.session_state.student_pending_confirm_seat = ""
                            with state["lock"]:
                                if not state["is_open"]:
                                    st.warning("老師剛剛已截止本題報名囉！")
                                else:
                                    state["candidates"][clean_seat] = time.time()
                                    save_persisted_state(state)
                            st.session_state.submitted_round = cur_round
                            st.rerun()
                    with cfm_c2:
                        if st.button("✏️ 不是，重新輸入", use_container_width=True, key="stu_confirm_no_btn"):
                            st.session_state.student_pending_confirm_seat = ""
                            st.session_state.student_saved_num = ""
                            st.rerun()
                else:
                    if st.button("🙋‍♂️ 我要舉手搶答！", type="primary", use_container_width=True):
                        if not clean_seat:
                            st.error("請先輸入你的座號！")
                        elif not is_confirmed_for_seat:
                            st.session_state.student_pending_confirm_seat = clean_seat
                            st.rerun()
                        else:
                            with state["lock"]:
                                if not state["is_open"]:
                                    st.warning("老師剛剛已截止本題報名囉！")
                                else:
                                    state["candidates"][clean_seat] = time.time()
                                    save_persisted_state(state)
                            st.session_state.submitted_round = cur_round
                            st.rerun()

        live_student_panel()