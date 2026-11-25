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
        padding: 10px 10px;
        margin: 6px;
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 4px;
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
        padding: 10px 10px;
        margin: 6px;
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 4px;
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
    .seat-card-box.last-adjusted {
        background: linear-gradient(180deg, #ecfdf5 0%, #d1fae5 100%) !important;
        border: 3px solid #10b981 !important;
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.25), 0 6px 14px rgba(16, 185, 129, 0.2) !important;
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

                if (!win.__seatingIframeObserverBound) {{
                    win.__seatingIframeObserverBound = true;
                    const obs = new MutationObserver(() => {{
                        doc.querySelectorAll('iframe').forEach((fr) => {{
                            try {{ attachComboToDoc(fr.contentDocument); }} catch (e) {{}}
                        }});
                    }});
                    obs.observe(doc.body, {{ childList: true, subtree: true }});
                }}
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
if "last_adjusted_seat" not in st.session_state:
    st.session_state.last_adjusted_seat = ""
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
    st.session_state.last_adjusted_seat = ""
    st.session_state["new_class_toast"] = True


def switch_active_class_slot(slot_key: str):
    if slot_key not in ("slot_1", "slot_2", "slot_3"):
        return
    with state["lock"]:
        state["active_slot"] = slot_key
        save_persisted_state(state)
    st.session_state.seating_undo_stack = []
    st.session_state.last_adjusted_seat = ""
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
    nonce = f"{time.time():.6f}_{random.randint(1000, 9999)}"
    js_code = f"""
    <script>
    /* trigger: {nonce} */
    (function() {{
        try {{
            if (window.parent && window.parent.__classDrawAudioEngine) {{
                window.parent.__classDrawAudioEngine.play("{kind}");
            }}
        }} catch (e) {{}}
    }})();
    </script>
    """
    components.html(js