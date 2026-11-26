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
    /* 學生端中籤通知卡片（與老師端聚光燈深靛藍＋金黃徽章風格一致） */
    .student-winner-banner {
        background: linear-gradient(135deg, #312e81 0%, #1e1b4b 55%, #0f172a 100%);
        border: 3px solid #facc15;
        border-radius: 20px;
        padding: 18px 16px;
        color: #ffffff;
        text-align: center;
        margin-bottom: 12px;
        box-shadow: 0 12px 26px rgba(30, 27, 75, 0.25);
    }
    .student-winner-rank-badge {
        display: inline-block;
        background: linear-gradient(180deg, #fde047 0%, #facc15 100%);
        color: #0f172a;
        border: 2px solid #ffffff;
        font-size: 0.92rem;
        font-weight: 900;
        padding: 3px 14px;
        border-radius: 999px;
        letter-spacing: 0.05em;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.22);
    }
    .student-winner-seat-num {
        font-size: 2.35rem;
        font-weight: 900;
        color: #fde047;
        line-height: 1.05;
        margin: 8px 0 4px 0;
        letter-spacing: 0.03em;
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
        tmp_file = DATA