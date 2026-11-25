import io
import os
import csv
import glob
import json
import time
import random
import html
import hashlib
from datetime import datetime
import threading
import streamlit as st
import streamlit.components.v1 as components

try:
    import qrcode
    from PIL import Image
    HAS_QR = True
except ImportError:
    HAS_QR = False


# ==========================================
# 1. 頁面設定與全域樣式（針對平板、投影大螢幕與手機優化）
# ==========================================
st.set_page_config(
    page_title="課堂即時搶答 × 座次計分系統",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
    /* 隱藏預設多餘選單，保留乾淨教學介面 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .block-container {
        padding-top: 0.9rem !important;
        padding-bottom: 1.5rem !important;
        max-width: 1460px !important;
    }

    /* 隱藏純音效/腳本 iframe 容器（脫離版面流，不佔高度且保持音訊可播放） */
    div[data-testid="stElementContainer"]:has(iframe[height="0"]),
    div.element-container:has(iframe[height="0"]) {
        position: fixed !important;
        left: -9999px !important;
        top: -9999px !important;
        width: 1px !important;
        height: 1px !important;
        opacity: 0 !important;
        pointer-events: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* 頂部標題列 */
    .top-banner {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 60%, #312e81 100%);
        color: #ffffff;
        padding: 14px 22px;
        border-radius: 16px;
        margin-bottom: 12px;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.16);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
    }
    .top-banner h1 {
        font-size: 1.45rem !important;
        font-weight: 800 !important;
        margin: 0 !important;
        letter-spacing: 0.4px;
        color: #ffffff !important;
    }
    .top-banner p {
        margin: 3px 0 0 0 !important;
        font-size: 0.86rem !important;
        color: #cbd5e1 !important;
    }
    .status-pill {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        padding: 6px 14px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.9rem;
        color: #f8fafc;
    }

    /* 主標題區塊 */
    .section-header {
        font-size: 1.08rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* 中籤大螢幕聚光燈看板（固定最小高度，確保輪轉與開獎之間零跳動） */
    .winner-spotlight {
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        border: 3px solid #2563eb;
        border-radius: 18px;
        padding: 16px 18px;
        text-align: center;
        box-shadow: 0 10px 24px rgba(37, 99, 235, 0.14);
        margin-bottom: 12px;
        min-height: 224px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }
    .winner-spotlight.rolling {
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
        border-color: #f59e0b;
        box-shadow: 0 10px 24px rgba(245, 158, 11, 0.18);
    }
    .winner-spotlight.empty {
        background: #f8fafc;
        border: 2px dashed #cbd5e1;
        box-shadow: none;
    }
    .winner-grid {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 12px;
        margin-top: 8px;
    }
    .winner-pill {
        background: #ffffff;
        border: 2px solid #2563eb;
        border-radius: 14px;
        padding: 10px 14px;
        width: 146px;
        min-width: 146px;
        height: 138px;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.12);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        align-items: center;
        box-sizing: border-box;
    }
    .winner-pill.rolling-pill {
        border-color: #f59e0b;
        background: #fffdf5;
    }
    .winner-pill-rank {
        font-size: 0.74rem;
        font-weight: 800;
        color: #1d4ed8;
        height: 18px;
        line-height: 18px;
        white-space: nowrap;
    }
    .winner-pill.rolling-pill .winner-pill-rank {
        color: #d97706;
    }
    .winner-pill-num {
        font-size: 2.3rem;
        font-weight: 900;
        color: #0f172a;
        line-height: 1.0;
        margin-bottom: 1px;
    }
    .winner-pill.rolling-pill .winner-pill-num {
        color: #b45309;
    }
    .winner-pill-footer {
        height: 44px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        width: 100%;
    }
    .winner-pill-name {
        font-size: 1.32rem;
        font-weight: 900;
        color: #1e293b;
        line-height: 1.15;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 130px;
    }
    .winner-pill.rolling-pill .winner-pill-name {
        color: #92400e;
    }

    /* 舉手池號碼徽章 */
    .candidate-pool {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 12px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        min-height: 76px;
        align-items: center;
    }
    .cand-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 10px;
        font-weight: 800;
        font-size: 0.98rem;
        background: #ffffff;
        border: 2px solid #3b82f6;
        color: #1e40af;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
    }
    .cand-badge.boosted {
        border-color: #10b981;
        background: #ecfdf5;
        color: #065f46;
    }
    .cand-badge .tag {
        font-size: 0.7rem;
        background: #10b981;
        color: white;
        padding: 2px 6px;
        border-radius: 999px;
    }

    /* 記分板卡片 */
    .score-card {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        margin-bottom: 6px;
    }
    .score-card.top-rank {
        background: linear-gradient(90deg, #fffbeb 0%, #ffffff 100%);
        border-color: #fbbf24;
    }
    .score-num {
        font-size: 1.05rem;
        font-weight: 800;
        color: #0f172a;
    }
    .score-pts {
        font-size: 1.02rem;
        font-weight: 900;
        color: #2563eb;
        background: #eff6ff;
        padding: 3px 10px;
        border-radius: 999px;
    }

    /* 全班座次表 8x8 座位卡片（走道強化分隔版） */
    .seat-card {
        border-radius: 10px;
        padding: 6px 4px 5px 4px;
        text-align: center;
        border: 1.5px solid #cbd5e1;
        background: #ffffff;
        box-shadow: 0 2px 4px rgba(15, 23, 42, 0.04);
        margin-bottom: 3px;
        min-height: 78px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .seat-card.empty-seat {
        background: #f8fafc;
        border: 1px dashed #cbd5e1;
        opacity: 0.65;
    }
    .seat-card.has-score {
        background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
        border-color: #3b82f6;
    }
    .seat-card.high-score {
        background: linear-gradient(180deg, #fef3c7 0%, #fffbeb 100%);
        border-color: #f59e0b;
        box-shadow: 0 3px 8px rgba(245, 158, 11, 0.18);
    }
    .seat-card.recent-winner {
        border: 2.5px solid #10b981;
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.25);
    }
    .seat-top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 3px;
        font-size: 0.72rem;
        font-weight: 800;
        color: #64748b;
    }
    .seat-score-pill {
        background: #2563eb;
        color: #ffffff;
        padding: 0px 6px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 900;
    }
    .seat-card.high-score .seat-score-pill {
        background: #d97706;
    }
    .seat-score-pill.zero {
        background: #e2e8f0;
        color: #64748b;
    }
    .seat-name {
        font-size: 0.94rem;
        font-weight: 900;
        color: #0f172a;
        margin: 2px 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .seat-class-tag {
        font-size: 0.65rem;
        color: #64748b;
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* 縱向走道分隔線（教室每2人一排，第2-3、4-5、6-7行之間加明顯走道） */
    .aisle-divider {
        width: 100%;
        height: 112px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        position: relative;
    }
    .aisle-divider::before {
        content: "";
        position: absolute;
        top: 2px;
        bottom: 2px;
        left: 50%;
        transform: translateX(-50%);
        width: 3px;
        background: repeating-linear-gradient(
            to bottom,
            #94a3b8 0px,
            #94a3b8 6px,
            transparent 6px,
            transparent 12px
        );
        border-radius: 2px;
        opacity: 0.65;
    }
    .aisle-label {
        background: #f1f5f9;
        color: #64748b;
        font-size: 0.64rem;
        font-weight: 800;
        padding: 2px 3px;
        border-radius: 4px;
        border: 1px solid #cbd5e1;
        z-index: 1;
        writing-mode: vertical-rl;
        letter-spacing: 1px;
    }

    /* 講台指示條 */
    .podium-bar {
        background: linear-gradient(90deg, #e2e8f0 0%, #cbd5e1 50%, #e2e8f0 100%);
        color: #334155;
        text-align: center;
        font-weight: 800;
        font-size: 0.88rem;
        padding: 7px 12px;
        border-radius: 10px;
        border: 1px solid #94a3b8;
        margin-bottom: 10px;
        letter-spacing: 2px;
    }

    /* 緊湊化座次表加減分小按鈕（手機與電腦並排不換行） */
    div[data-testid="stButton"] button {
        border-radius: 10px !important;
        font-weight: 800 !important;
    }

    /* 教師密碼解鎖卡片 */
    .lock-card {
        max-width: 440px;
        margin: 28px auto;
        background: #ffffff;
        border: 2px solid #cbd5e1;
        border-radius: 20px;
        padding: 28px 24px;
        text-align: center;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
    }

    /* 手機版自動調整 */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 0.45rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        .top-banner {
            padding: 10px 14px;
            border-radius: 12px;
            margin-bottom: 8px;
        }
        .top-banner h1 {
            font-size: 1.12rem !important;
        }
        .winner-pill {
            width: 118px;
            min-width: 118px;
            height: 122px;
            padding: 8px 8px;
        }
        .winner-pill-num {
            font-size: 1.85rem;
        }
        .winner-pill-name {
            font-size: 1.15rem;
            max-width: 104px;
        }
        .seat-card {
            min-height: 68px;
            padding: 4px 2px;
        }
        .seat-name {
            font-size: 0.8rem;
        }
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==========================================
# 1.5 座次表連點即時浮動氣泡引擎（支援多層 iframe 精準定位 + 動態重繪監聽）
# ==========================================
def inject_seating_combo_bubble():
    """
    注入外層主視窗全域連點氣泡引擎與共用 AudioContext 解鎖器：
    - 滑鼠移過去（Hover）完全不彈出任何提示。
    - 真正點擊座次表 ➕ / ➖ 時，在該按鈕正上方即時彈出金色連點累加氣泡（01 莊子萱 +1 分 → +2 分 → +3 分）。
    """
    components.html(
        """
        <script>
        (function() {
            try {
                const win = window.parent || window;
                const doc = win.document;

                // 1. 全域共用 Web Audio 解鎖器（讓後續抽籤與加減分音效 100% 必響）
                if (!win.__classDrawAudioInit) {
                    win.__classDrawAudioInit = true;
                    win.getClassDrawAudioCtx = function() {
                        const AudioCtx = win.AudioContext || win.webkitAudioContext;
                        if (!AudioCtx) return null;
                        if (!win.__classDrawCtx) {
                            win.__classDrawCtx = new AudioCtx();
                        }
                        if (win.__classDrawCtx.state === 'suspended') {
                            win.__classDrawCtx.resume().catch(function(){});
                        }
                        return win.__classDrawCtx;
                    };
                    ['pointerdown', 'touchstart', 'click', 'keydown'].forEach(function(evtName) {
                        doc.addEventListener(evtName, function() {
                            if (win.getClassDrawAudioCtx) win.getClassDrawAudioCtx();
                        }, { capture: true, passive: true });
                    });
                }

                // 2. 注入金色連點累加氣泡樣式
                if (!doc.getElementById('seating-combo-bubble-style')) {
                    const st = doc.createElement('style');
                    st.id = 'seating-combo-bubble-style';
                    st.textContent = `
                        #seating-combo-bubble {
                            position: fixed;
                            z-index: 2147483647;
                            pointer-events: none;
                            padding: 7px 14px;
                            border-radius: 999px;
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                            font-size: 14px;
                            font-weight: 900;
                            letter-spacing: 0.3px;
                            white-space: nowrap;
                            color: #ffffff;
                            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                            border: 2px solid #fef3c7;
                            box-shadow: 0 10px 24px rgba(217, 119, 6, 0.45), 0 0 0 3px rgba(251, 191, 36, 0.28);
                            transform: translate(-50%, -100%) scale(0.85);
                            opacity: 0;
                            transition: opacity 0.16s ease, transform 0.18s cubic-bezier(0.22, 1, 0.36, 1);
                        }
                        #seating-combo-bubble.minus-mode {
                            background: linear-gradient(135deg, #475569 0%, #1e293b 100%);
                            border-color: #cbd5e1;
                            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.4);
                        }
                        #seating-combo-bubble.visible {
                            opacity: 1;
                            transform: translate(-50%, -115%) scale(1.0);
                        }
                        #seating-combo-bubble.pop {
                            transform: translate(-50%, -124%) scale(1.12);
                        }
                    `;
                    doc.head.appendChild(st);
                }

                // 3. 建立或取得唯一的氣泡 DOM
                win.showSeatingComboBubble = function(rectLeft, rectTop, seatNum, stuName, delta) {
                    let bubble = doc.getElementById('seating-combo-bubble');
                    if (!bubble) {
                        bubble = doc.createElement('div');
                        bubble.id = 'seating-combo-bubble';
                        doc.body.appendChild(bubble);
                    }

                    const now = Date.now();
                    if (!win.__comboState) {
                        win.__comboState = { seat: '', total: 0, lastAt: 0 };
                    }
                    if (win.__comboState.seat === seatNum && (now - win.__comboState.lastAt) < 2000) {
                        win.__comboState.total += delta;
                    } else {
                        win.__comboState.seat = seatNum;
                        win.__comboState.total = delta;
                    }
                    win.__comboState.lastAt = now;

                    const tot = win.__comboState.total;
                    const signStr = tot >= 0 ? ('+' + tot) : ('' + tot);
                    const labelName = stuName ? (' ' + stuName) : '';
                    bubble.textContent = seatNum + labelName + '  ' + signStr + ' 分';

                    if (tot < 0) {
                        bubble.classList.add('minus-mode');
                    } else {
                        bubble.classList.remove('minus-mode');
                    }

                    const safeX = Math.max(85, Math.min(win.innerWidth - 85, rectLeft));
                    const safeY = Math.max(48, rectTop - 6);
                    bubble.style.left = safeX + 'px';
                    bubble.style.top = safeY + 'px';

                    bubble.classList.remove('pop');
                    bubble.classList.add('visible');
                    void bubble.offsetWidth;
                    bubble.classList.add('pop');
                    setTimeout(function() {
                        if (bubble) bubble.classList.remove('pop');
                    }, 160);

                    if (win.__comboHideTimer) clearTimeout(win.__comboHideTimer);
                    win.__comboHideTimer = setTimeout(function() {
                        if (bubble) bubble.classList.remove('visible');
                    }, 1850);
                };

                // 4. 在外層主文件綁定捕獲階段點擊監聽（自動往上找座位卡片並換算嵌套 iframe 座標）
                if (!win.__seatingComboBubbleBoundV3) {
                    win.__seatingComboBubbleBoundV3 = true;

                    function extractSeatInfoFromButton(btn) {
                        let cur = btn.parentElement;
                        for (let depth = 0; depth < 7 && cur; depth++) {
                            const card = cur.querySelector('.seat-card');
                            if (card) {
                                const topRow = card.querySelector('.seat-top-row');
                                const nameEl = card.querySelector('.seat-name');
                                let seatNum = '';
                                if (topRow) {
                                    const m = (topRow.textContent || '').match(/(\d{2})/);
                                    if (m) seatNum = m[1];
                                }
                                let stuName = nameEl ? (nameEl.textContent || '').trim() : '';
                                if (stuName === '(空位)') stuName = '';
                                return { seatNum: seatNum, stuName: stuName };
                            }
                            cur = cur.parentElement;
                        }
                        return null;
                    }

                    function attachListenerToDoc(targetDoc, frameOffsetFn) {
                        if (!targetDoc || targetDoc.__seatingClickHooked) return;
                        targetDoc.__seatingClickHooked = true;

                        targetDoc.addEventListener('pointerdown', function(e) {
                            const btn = e.target && e.target.closest ? e.target.closest('button') : null;
                            if (!btn) return;
                            const txt = (btn.innerText || btn.textContent || '').trim();
                            if (txt !== '➕' && txt !== '➖') return;

                            const info = extractSeatInfoFromButton(btn);
                            if (!info || !info.seatNum) return;

                            const rect = btn.getBoundingClientRect();
                            const offset = frameOffsetFn ? frameOffsetFn() : { x: 0, y: 0 };
                            const centerX = offset.x + rect.left + rect.width / 2;
                            const topY = offset.y + rect.top;
                            const delta = (txt === '➕') ? 1 : -1;

                            win.showSeatingComboBubble(centerX, topY, info.seatNum, info.stuName, delta);
                        }, true);
                    }

                    attachListenerToDoc(doc, function() { return { x: 0, y: 0 }; });

                    // 定期掃描並清除任何殘留的原生 title 懸停提示，同時掛載同源子 iframe
                    setInterval(function() {
                        try {
                            const btns = doc.querySelectorAll('button[title]');
                            btns.forEach(function(b) {
                                const t = (b.innerText || '').trim();
                                if (t === '➕' || t === '➖') {
                                    b.removeAttribute('title');
                                }
                            });
                            const iframes = doc.querySelectorAll('iframe');
                            iframes.forEach(function(ifr) {
                                try {
                                    if (ifr.contentDocument) {
                                        attachListenerToDoc(ifr.contentDocument, function() {
                                            const r = ifr.getBoundingClientRect();
                                            return { x: r.left, y: r.top };
                                        });
                                    }
                                } catch (err) {}
                            });
                        } catch (err) {}
                    }, 900);
                }
            } catch (e) {}
        })();
        </script>
        """,
        height=0,
    )


# ==========================================
# 2. 音效產生器（使用外層主視窗共用 Web Audio 引擎，100% 必響且零跳動）
# ==========================================
def play_sound_effect(kind="fanfare", enabled=True):
    """透過外層主視窗共用的 AudioContext 播放純淨音效（附唯一時間戳確保每次重繪必觸發）"""
    if not enabled:
        return
    nonce = f"{time.time():.6f}_{random.randint(1000, 9999)}"
    if kind == "rolling":
        js_code = f"""
        <script>
        /* rolling_ts: {nonce} */
        (function() {{
            try {{
                const win = window.parent || window;
                const ctx = win.getClassDrawAudioCtx ? win.getClassDrawAudioCtx() : null;
                if (!ctx) return;
                const notes = [523.25, 659.25, 783.99, 659.25, 587.33, 739.99, 880.00, 1046.50];
                notes.forEach((freq, idx) => {{
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'triangle';
                    osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.085);
                    gain.gain.setValueAtTime(0.14, ctx.currentTime + idx * 0.085);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.085 + 0.075);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(ctx.currentTime + idx * 0.085);
                    osc.stop(ctx.currentTime + idx * 0.085 + 0.08);
                }});
            }} catch(e) {{}}
        }})();
        </script>
        """
    else:
        js_code = f"""
        <script>
        /* fanfare_ts: {nonce} */
        (function() {{
            try {{
                const win = window.parent || window;
                const ctx = win.getClassDrawAudioCtx ? win.getClassDrawAudioCtx() : null;
                if (!ctx) return;
                const chord = [
                    {{ freq: 523.25, delay: 0.00, dur: 0.14 }},
                    {{ freq: 659.25, delay: 0.11, dur: 0.14 }},
                    {{ freq: 783.99, delay: 0.22, dur: 0.16 }},
                    {{ freq: 1046.50, delay: 0.34, dur: 0.48 }}
                ];
                chord.forEach(item => {{
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(item.freq, ctx.currentTime + item.delay);
                    gain.gain.setValueAtTime(0.24, ctx.currentTime + item.delay);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + item.delay + item.dur);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(ctx.currentTime + item.delay);
                    osc.stop(ctx.currentTime + item.delay + item.dur + 0.02);
                }});
            }} catch(e) {{}}
        }})();
        </script>
        """
    components.html(js_code, height=0)


def play_seating_click_feedback(delta=1, enabled=True):
    """座次表加減分：觸發極簡純淨單音與手機震動回饋"""
    nonce = f"{time.time():.6f}_{random.randint(1000, 9999)}"
    vibrate_js = "navigator.vibrate([60]);" if delta > 0 else "navigator.vibrate([50, 40, 60]);"
    freq = 1000 if delta > 0 else 520
    sound_js = ""
    if enabled:
        sound_js = f"""
        const win = window.parent || window;
        const ctx = win.getClassDrawAudioCtx ? win.getClassDrawAudioCtx() : null;
        if (ctx) {{
            const now = ctx.currentTime;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime({freq}, now);
            gain.gain.setValueAtTime(0.001, now);
            gain.gain.linearRampToValueAtTime(0.32, now + 0.008);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.075);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.08);
        }}
        """
    js_code = f"""
    <script>
    /* click_ts: {nonce} */
    (function() {{
        try {{
            if (navigator && typeof navigator.vibrate === 'function') {{
                {vibrate_js}
            }}
            {sound_js}
        }} catch(e) {{}}
    }})();
    </script>
    """
    components.html(js_code, height=0)


# ==========================================
# 3. 密碼雜湊與狀態持久化（防止重新整理遺失 + 自動回補 GitHub 預設名單）
# ==========================================
STATE_FILE = "class_draw_state.json"
DEFAULT_ADMIN_PASSCODE = "1234"
DEFAULT_ROSTER_SLOTS = ["slot_1", "slot_2", "slot_3"]


def hash_passcode(raw_code: str) -> str:
    """將教師密碼進行 SHA-256 雜湊儲存"""
    return hashlib.sha256(f"class_draw_salt::{raw_code.strip()}".encode("utf-8")).hexdigest()


def normalize_seat_num(raw_val) -> str:
    """標準化座號格式（例如 '5' -> '05', '12' -> '12'）"""
    if raw_val is None:
        return ""
    s = str(raw_val).strip()
    if not s:
        return ""
    if s.isdigit():
        return f"{int(s):02d}"
    return s.upper()


def parse_csv_roster(file_bytes: bytes):
    """解析班級名單 CSV（支援 UTF-8 BOM / Big5 / 舊名單與多週累計總表）"""
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = file_bytes.decode("utf-8", errors="ignore")

    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return {}, [], "班級"

    header = [h.strip() for h in rows[0]]
    has_header = False
    idx_class, idx_num, idx_name, idx_sem_total = 0, 1, 2, -1
    date_cols = []

    for i, col in enumerate(header):
        if "班級" in col or col.lower() in ("class", "class_name"):
            idx_class = i
            has_header = True
        elif "座號" in col or "學號" in col or col.lower() in ("seat", "number", "no", "id"):
            idx_num = i
            has_header = True
        elif "姓名" in col or "名字" in col or col.lower() in ("name", "student"):
            idx_name = i
            has_header = True
        elif "學期總" in col or "累計總" in col or col.lower() in ("total", "semester_total"):
            idx_sem_total = i
            has_header = True

    start_row = 1 if has_header else 0
    if has_header:
        used_indices = {idx_class, idx_num, idx_name}
        if idx_sem_total >= 0:
            used_indices.add(idx_sem_total)
        for i, col in enumerate(header):
            if i not in used_indices and col:
                date_cols.append((i, col))

    roster_dict = {}
    detected_classes = []

    for r in rows[start_row:]:
        if len(r) <= max(idx_num, idx_name):
            continue
        cls_name = r[idx_class].strip() if idx_class < len(r) else ""
        seat_num = normalize_seat_num(r[idx_num])
        stu_name = r[idx_name].strip() if idx_name < len(r) else ""

        if not seat_num or not stu_name:
            continue

        if cls_name and cls_name not in detected_classes:
            detected_classes.append(cls_name)

        daily_records = {}
        for col_idx, col_label in date_cols:
            if col_idx < len(r):
                raw_val = r[col_idx].strip()
                if raw_val != "":
                    try:
                        daily_records[col_label] = int(float(raw_val))
                    except ValueError:
                        pass

        sem_total = sum(daily_records.values())
        if idx_sem_total >= 0 and idx_sem_total < len(r) and not daily_records:
            raw_tot = r[idx_sem_total].strip()
            if raw_tot != "":
                try:
                    sem_total = int(float(raw_tot))
                except ValueError:
                    sem_total = 0

        roster_dict[seat_num] = {
            "class_name": cls_name,
            "name": stu_name,
            "semester_total": sem_total,
            "daily_records": daily_records,
        }

    ordered_dates = [label for _, label in date_cols]
    summary_label = " / ".join(detected_classes[:2]) if detected_classes else "未命名班級"
    if len(detected_classes) > 2:
        summary_label += f" 等{len(detected_classes)}班"
    return roster_dict, ordered_dates, summary_label


def load_default_rosters_from_github():
    """
    從 GitHub 倉庫預存的 default_rosters 資料夾、default_rosters.json 或根目錄 CSV 自動載入三個班級預設名單。
    回傳 dict: { "slot_1": {...}, "slot_2": {...}, "slot_3": {...} }
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    result = {}

    # 1. 優先檢查 default_rosters.json
    json_candidates = [
        os.path.join(base_dir, "default_rosters.json"),
        os.path.join(base_dir, "default_rosters", "default_rosters.json"),
    ]
    for jp in json_candidates:
        if os.path.exists(jp):
            try:
                with open(jp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for idx, slot_key in enumerate(DEFAULT_ROSTER_SLOTS):
                        if slot_key in data and isinstance(data[slot_key], dict):
                            result[slot_key] = data[slot_key]
                    if result:
                        return result
            except Exception:
                pass

    # 2. 搜尋 default_rosters/ 資料夾內的所有 .csv，或倉庫根目錄的班級 .csv
    csv_files = []
    default_dir = os.path.join(base_dir, "default_rosters")
    if os.path.isdir(default_dir):
        csv_files = sorted(glob.glob(os.path.join(default_dir, "*.csv")))

    if not csv_files:
        # 尋找倉庫根目錄下符合 slot_1 / roster_1 或一般班級名單的 CSV（排除空白範本）
        all_root_csv = sorted(glob.glob(os.path.join(base_dir, "*.csv")))
        csv_files = [
            p for p in all_root_csv
            if "template" not in os.path.basename(p).lower()
            and "範本" not in os.path.basename(p)
        ]

    for idx, csv_path in enumerate(csv_files[:3]):
        slot_key = DEFAULT_ROSTER_SLOTS[idx]
        try:
            with open(csv_path, "rb") as f:
                raw_bytes = f.read()
            parsed_students, parsed_dates, parsed_label = parse_csv_roster(raw_bytes)
            if parsed_students:
                file_stem = os.path.splitext(os.path.basename(csv_path))[0]
                display_label = parsed_label if parsed_label != "未命名班級" else file_stem
                result[slot_key] = {
                    "label": display_label,
                    "students": parsed_students,
                    "dates": parsed_dates,
                }
        except Exception:
            continue

    return result


def ensure_default_rosters_populated(rosters_dict: dict) -> tuple[dict, bool]:
    """若任何班級槽位為空，自動從 GitHub 預存 default_rosters 補回"""
    if not isinstance(rosters_dict, dict):
        rosters_dict = {}
    need_fallback = any(
        not rosters_dict.get(slot, {}).get("students")
        for slot in DEFAULT_ROSTER_SLOTS
    )
    if not need_fallback:
        return rosters_dict, False

    github_defaults = load_default_rosters_from_github()
    changed = False
    for idx, slot in enumerate(DEFAULT_ROSTER_SLOTS):
        cur_slot = rosters_dict.get(slot)
        if not isinstance(cur_slot, dict) or not cur_slot.get("students"):
            if slot in github_defaults and github_defaults[slot].get("students"):
                rosters_dict[slot] = github_defaults[slot]
                changed = True
            elif not isinstance(cur_slot, dict):
                rosters_dict[slot] = {"label": f"班級 {idx + 1}", "students": {}, "dates": []}
                changed = True
        else:
            if "label" not in cur_slot or not cur_slot["label"]:
                cur_slot["label"] = f"班級 {idx + 1}"
                changed = True
            if "dates" not in cur_slot:
                cur_slot["dates"] = []
                changed = True
    return rosters_dict, changed


def load_persisted_state():
    """從本地 JSON 檔案讀取已儲存的班級名單、分數與設定；若名單為空則自動從 GitHub default_rosters 補回"""
    default_rosters = {
        "slot_1": {"label": "班級 1", "students": {}, "dates": []},
        "slot_2": {"label": "班級 2", "students": {}, "dates": []},
        "slot_3": {"label": "班級 3", "students": {}, "dates": []},
    }
    default_rosters, _ = ensure_default_rosters_populated(default_rosters)

    default_data = {
        "round": 1,
        "is_open": True,
        "candidates": {},
        "scores": {},
        "history": {},
        "last_winners": [],
        "last_points_awarded": 0,
        "student_share_url": "https://class-draw.streamlit.app/",
        "admin_passcode_hash": hash_passcode(DEFAULT_ADMIN_PASSCODE),
        "active_roster_slot": "slot_1",
        "rosters": default_rosters,
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                for k in default_data:
                    if k in saved:
                        default_data[k] = saved[k]
                for slot_key in DEFAULT_ROSTER_SLOTS:
                    if slot_key not in default_data["rosters"]:
                        default_data["rosters"][slot_key] = default_rosters[slot_key]
                    elif "dates" not in default_data["rosters"][slot_key]:
                        default_data["rosters"][slot_key]["dates"] = []
                default_data["rosters"], _ = ensure_default_rosters_populated(default_data["rosters"])
        except Exception:
            pass
    return default_data


def save_persisted_state(state_dict):
    """將核心課堂狀態同步寫入本地 JSON 檔案"""
    try:
        payload = {
            "round": state_dict["round"],
            "is_open": state_dict["is_open"],
            "candidates": state_dict["candidates"],
            "scores": state_dict["scores"],
            "history": state_dict["history"],
            "last_winners": state_dict["last_winners"],
            "last_points_awarded": state_dict["last_points_awarded"],
            "student_share_url": state_dict.get("student_share_url", "https://class-draw.streamlit.app/"),
            "admin_passcode_hash": state_dict.get("admin_passcode_hash", hash_passcode(DEFAULT_ADMIN_PASSCODE)),
            "active_roster_slot": state_dict["active_roster_slot"],
            "rosters": state_dict["rosters"],
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ==========================================
# 4. 全域跨裝置即時共享狀態（老師端與全班學生手機端即時連動）
# ==========================================
@st.cache_resource
def get_classroom_state():
    loaded = load_persisted_state()
    loaded["lock"] = threading.Lock()
    return loaded


state = get_classroom_state()

# 若執行期間名單意外被清空，自動從 GitHub default_rosters 補回
with state["lock"]:
    state["rosters"], _restored_flag = ensure_default_rosters_populated(state["rosters"])
    if _restored_flag:
        save_persisted_state(state)


# 初始化本地端 Session 狀態
if "student_saved_num" not in st.session_state:
    st.session_state.student_saved_num = ""
if "student_confirmed_seat" not in st.session_state:
    st.session_state.student_confirmed_seat = ""
if "student_pending_confirm_seat" not in st.session_state:
    st.session_state.student_pending_confirm_seat = ""
if "submitted_round" not in st.session_state:
    st.session_state.submitted_round = 0
if "play_fanfare_once" not in st.session_state:
    st.session_state.play_fanfare_once = False
if "seating_feedback_delta" not in st.session_state:
    st.session_state.seating_feedback_delta = 0
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False
if "show_passcode_settings" not in st.session_state:
    st.session_state.show_passcode_settings = False
if "student_last_known_score" not in st.session_state:
    st.session_state.student_last_known_score = None
if "student_score_gain_banner" not in st.session_state:
    st.session_state.student_score_gain_banner = None
if "pending_csv_preview" not in st.session_state:
    st.session_state.pending_csv_preview = None


# ==========================================
# 5. URL 參數分流（學生端預設免密碼；老師端網址 ?mode=admin 需輸入密碼解鎖）
# ==========================================
query_params = st.query_params
raw_mode = query_params.get("mode", "student")
if isinstance(raw_mode, list):
    raw_mode = raw_mode[0] if raw_mode else "student"

is_admin_url = (str(raw_mode).lower() == "admin")


# ==========================================
# 6. 核心邏輯輔助函式（名單解析、多週累計結算、總表匯出、抽籤與計分）
# ==========================================
def get_active_roster_info():
    """取得目前選取班級的 slot、名稱、學生名單字典與日期欄位清單"""
    slot = state.get("active_roster_slot", "slot_1")
    slot_data = state["rosters"].get(slot, {"label": "班級 1", "students": {}, "dates": []})
    return (
        slot,
        slot_data.get("label", "班級 1"),
        slot_data.get("students", {}),
        slot_data.get("dates", []),
    )


def format_student_badge(seat_num: str, roster: dict, include_class: bool = False) -> str:
    """組合座號與學生姓名顯示文字"""
    info = roster.get(seat_num)
    if not info:
        return f"{seat_num} 號"
    name = info.get("name", "")
    cls = info.get("class_name", "")
    if include_class and cls:
        return f"{seat_num} {name} ({cls})"
    return f"{seat_num} {name}".strip()


def generate_template_csv() -> bytes:
    """產生 01~64 號空白班級名單 CSV 範本（UTF-8 BOM）"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["班級", "座號", "姓名"])
    sample_names = {1: "王小明", 2: "陳思穎", 3: "林冠宇"}
    for i in range(1, 65):
        writer.writerow(["範例班級一甲", f"{i:02d}", sample_names.get(i, "")])
    return output.getvalue().encode("utf-8-sig")


def generate_gradebook_csv(slot_key: str) -> bytes:
    """匯出該班級完整的『學期累計成績總表 CSV』（固定輸出 01～64 號完整行列）"""
    slot_data = state["rosters"].get(slot_key, {"label": "班級", "students": {}, "dates": []})
    students = slot_data.get("students", {})
    dates = slot_data.get("dates", [])
    default_cls_name = slot_data.get("label", "")

    for stu in students.values():
        if stu.get("class_name"):
            default_cls_name = stu.get("class_name")
            break

    output = io.StringIO()
    writer = csv.writer(output)
    header = ["班級", "座號", "姓名", "學期總加分"] + list(dates)
    writer.writerow(header)

    for i in range(1, 65):
        seat = f"{i:02d}"
        stu = students.get(seat)
        if stu:
            daily = stu.get("daily_records", {})
            sem_total = sum(daily.values()) if dates else int(stu.get("semester_total", 0))
            row = [stu.get("class_name", default_cls_name), seat, stu.get("name", ""), sem_total]
            for d in dates:
                row.append(daily.get(d, ""))
        else:
            row = [default_cls_name, seat, "", 0] + ["" for _ in dates]
        writer.writerow(row)

    return output.getvalue().encode("utf-8-sig")


def settle_today_scores_to_roster(slot_key: str, date_label: str, reset_today: bool = True):
    """將今日即時分數結算寫入該班級的指定日期欄位，並重新計算學期總加分"""
    clean_date = date_label.strip() or datetime.now().strftime("%Y/%m/%d")
    with state["lock"]:
        slot_data = state["rosters"].get(slot_key)
        if not slot_data:
            return False, "找不到班級資料"
        students = slot_data.get("students", {})
        if not students:
            return False, "目前班級尚未匯入名單，無法寫入總表"

        dates = slot_data.setdefault("dates", [])
        if clean_date not in dates:
            dates.append(clean_date)

        for seat, stu in students.items():
            today_pts = int(state["scores"].get(seat, 0))
            daily = stu.setdefault("daily_records", {})
            daily[clean_date] = int(daily.get(clean_date, 0)) + today_pts
            stu["semester_total"] = sum(daily.values())

        if reset_today:
            state["scores"].clear()
            state["history"].clear()
            state["last_winners"] = []
            state["last_points_awarded"] = 0

        save_persisted_state(state)
    return True, f"已成功將今日得分寫入【{clean_date}】欄位並更新學期總加分！"


def pick_weighted_candidates(pool_list, history_dict, count=1, weighted=True):
    """從候選池抽出指定人數（未抽中過者享有 3 倍權重）"""
    pool = list(pool_list)
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


def build_qr_image(url_text: str):
    if not HAS_QR:
        return None
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def adjust_seat_score(seat_num: str, delta: int):
    """座次表加減分專用函式（記錄歷史並觸發音效與震動）"""
    with state["lock"]:
        cur = state["scores"].get(seat_num, 0)
        state["scores"][seat_num] = cur + delta
        if delta > 0:
            state["history"][seat_num] = state["history"].get(seat_num, 0) + 1
        save_persisted_state(state)
    st.session_state.seating_feedback_delta = delta


# ==========================================
# 7. 學生手機端專屬畫面（預設開啟，完全看不到老師密碼與後台）
# ==========================================
if not is_admin_url:
    _, active_cls_label, _, _ = get_active_roster_info()
    st.markdown(
        f"""
        <div class="top-banner">
            <div>
                <h1>🙋‍♂️ 課堂即時搶答</h1>
                <p>目前班級：<b>{html.escape(active_cls_label)}</b> ｜ 輸入座號點擊確認，準備搶答時再按舉手</p>
            </div>
            <div class="status-pill">📱 學生端</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center_col, _ = st.columns([1, 2.2, 1])
    with center_col:

        @st.fragment(run_every=2.0)
        def live_student_panel():
            with state["lock"]:
                cur_round = state["round"]
                is_open = state["is_open"]
                cand_count = len(state["candidates"])
                _, cls_label, roster, _ = get_active_roster_info()

            st.markdown(
                f"""
                <div style="background:#ffffff; border:2px solid #e2e8f0; border-radius:16px; padding:14px 16px; margin-bottom:12px; text-align:center;">
                    <div style="font-size:0.86rem; color:#64748b; font-weight:700;">目前進行題次（{html.escape(cls_label)}）</div>
                    <div style="font-size:1.75rem; font-weight:900; color:#1e3a8a; margin:2px 0;">第 {cur_round} 題</div>
                    <div style="font-size:0.88rem; font-weight:700; color:{'#059669' if is_open else '#dc2626'};">
                        {'🟢 開放舉手中（目前 ' + str(cand_count) + ' 人排隊）' if is_open else '🔴 本題已截止舉手'}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 若學生已確認綁定座號，頂部顯示個人今日得分看板（不顯示學期累計總分）
            saved_seat = st.session_state.student_saved_num
            confirmed_seat = st.session_state.student_confirmed_seat
            if saved_seat and confirmed_seat == saved_seat:
                today_sc = int(state["scores"].get(saved_seat, 0))
                stu_rec = roster.get(saved_seat, {})
                stu_nm = stu_rec.get("name", "")

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
                    f'<div style="font-size:1.25rem; font-weight:900; color:#1e1b4b;">{saved_seat} 號 {html.escape(stu_nm)}</div></div>'
                    f'<div style="text-align:right;">'
                    f'<div style="background:#4f46e5; color:#ffffff; font-size:0.95rem; font-weight:900; padding:4px 14px; border-radius:999px;">今日 {today_sc} 分</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

            with st.container(border=True):
                raw_seat = st.text_input(
                    "請輸入你的座號（例如：05 或 12）",
                    value=st.session_state.student_saved_num,
                    placeholder="輸入座號後點擊確認",
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

                if clean_seat and not is_confirmed_for_seat:
                    # 尚未確認綁定此座號時，先顯示身分確認卡片與純「確認」按鈕（不直接送出抽籤）
                    stu_info = roster.get(clean_seat, {})
                    stu_name = stu_info.get("name", "").strip()
                    stu_cls = stu_info.get("class_name", "").strip()
                    if stu_name:
                        cls_prefix = f"{html.escape(stu_cls)} · " if stu_cls else ""
                        confirm_html = (
                            f'<div style="background:#fffbeb; border:2px solid #f59e0b; border-radius:14px; padding:14px 16px; margin-bottom:10px; text-align:center;">'
                            f'<div style="font-size:0.84rem; font-weight:800; color:#b45309;">🔍 請確認你的身分</div>'
                            f'<div style="font-size:1.35rem; font-weight:900; color:#0f172a; margin-top:4px;">{cls_prefix}{clean_seat} 號 · {html.escape(stu_name)}</div>'
                            f'<div style="font-size:0.8rem; color:#64748b; margin-top:4px;">點擊「確認」後將先顯示目前得分，不會直接送出抽籤</div>'
                            f'</div>'
                        )
                    else:
                        confirm_html = (
                            f'<div style="background:#fffbeb; border:2px solid #f59e0b; border-radius:14px; padding:14px 16px; margin-bottom:10px; text-align:center;">'
                            f'<div style="font-size:0.84rem; font-weight:800; color:#b45309;">🔍 請確認你的座號</div>'
                            f'<div style="font-size:1.35rem; font-weight:900; color:#0f172a; margin-top:4px;">座號：{clean_seat} 號（名單未建檔）</div>'
                            f'<div style="font-size:0.8rem; color:#64748b; margin-top:4px;">點擊「確認」後將先顯示目前得分，不會直接送出抽籤</div>'
                            f'</div>'
                        )
                    st.markdown(confirm_html, unsafe_allow_html=True)

                    cfm_c1, cfm_c2 = st.columns(2)
                    with cfm_c1:
                        if st.button("✅ 確認", type="primary", use_container_width=True, key="stu_confirm_yes_btn"):
                            st.session_state.student_confirmed_seat = clean_seat
                            st.session_state.student_pending_confirm_seat = ""
                            st.session_state.student_last_known_score = int(state["scores"].get(clean_seat, 0))
                            st.rerun()
                    with cfm_c2:
                        if st.button("✏️ 重新輸入", use_container_width=True, key="stu_confirm_no_btn"):
                            st.session_state.student_pending_confirm_seat = ""
                            st.session_state.student_saved_num = ""
                            st.rerun()
                elif is_winner_now:
                    winner_rank = last_winners_list.index(clean_seat) + 1
                    st.success(f"🎉 恭喜 **{clean_seat} 號**！你是 **第 {winner_rank} 位** 中籤發言同學，請準備回答！")
                elif already_in_pool:
                    st.info(f"🙋 **{clean_seat} 號** 已在「第 {cur_round} 題」舉手名單中，請靜候老師抽籤！")
                elif not is_open:
                    st.warning("⏸️ 本題目前暫停舉手報名，請等待老師開啟下一題。")
                else:
                    if st.button("🙋‍♂️ 我要舉手搶答！", type="primary", use_container_width=True):
                        if not clean_seat:
                            st.error("請先輸入你的座號！")
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


# ==========================================
# 8. 老師端控制台（網址需帶 ?mode=admin 且通過密碼鎖驗證）
# ==========================================
else:
    if not st.session_state.admin_authenticated:
        st.markdown(
            """
            <div class="top-banner">
                <div>
                    <h1>🔐 老師控制台安全驗證</h1>
                    <p>請輸入教師端解鎖密碼以進入「抽籤主控台」與「全班座次記分系統」</p>
                </div>
                <div class="status-pill">🔒 已上鎖</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container():
            st.markdown(
                """
                <div class="lock-card">
                    <div style="font-size:2.4rem; margin-bottom:6px;">🛡️</div>
                    <div style="font-size:1.25rem; font-weight:900; color:#0f172a; margin-bottom:4px;">教師控制台密碼鎖</div>
                    <div style="font-size:0.86rem; color:#64748b; margin-bottom:16px;">預設密碼為 <b>1234</b>（解鎖後可於右上角隨時修改密碼）</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            _, lock_col, _ = st.columns([1.2, 1.4, 1.2])
            with lock_col:
                with st.form("admin_unlock_form", clear_on_submit=False):
                    pwd_input = st.text_input(
                        "請輸入老師端密碼",
                        type="password",
                        placeholder="輸入密碼（預設 1234）",
                    )
                    unlock_submitted = st.form_submit_button("🔓 解鎖進入老師端", type="primary", use_container_width=True)
                    if unlock_submitted:
                        stored_hash = state.get("admin_passcode_hash", hash_passcode(DEFAULT_ADMIN_PASSCODE))
                        if hash_passcode(pwd_input) == stored_hash:
                            st.session_state.admin_authenticated = True
                            st.rerun()
                        else:
                            st.error("❌ 密碼錯誤，請重新輸入！")

                with st.expander("❓ 忘記密碼？重設為預設密碼 (1234)"):
                    st.caption("若忘記自訂密碼，可點擊下方按鈕將教師端密碼恢復為 `1234`（不會清除班級名單與分數）。")
                    if st.button("🔄 重設密碼為 1234", use_container_width=True):
                        with state["lock"]:
                            state["admin_passcode_hash"] = hash_passcode(DEFAULT_ADMIN_PASSCODE)
                            save_persisted_state(state)
                        st.success("✅ 密碼已重設為 1234，請在上方輸入 1234 解鎖！")
        st.stop()

    # ------------------------------------------
    # 已解鎖：老師端完整雙分頁主畫面
    # ------------------------------------------
    # 注入全域連點累加氣泡引擎與 AudioContext 解鎖器
    inject_seating_combo_bubble()

    active_slot, active_cls_label, active_roster, active_dates = get_active_roster_info()

    # 若剛從座次表點擊加減分，觸發對應單音與震動
    if st.session_state.seating_feedback_delta != 0:
        fb_delta = st.session_state.seating_feedback_delta
        st.session_state.seating_feedback_delta = 0
        play_seating_click_feedback(delta=fb_delta, enabled=st.session_state.get("sound_on_toggle", True))

    # 頂部橫幅 + 右上角功能操作
    hdr_col1, hdr_col2 = st.columns([3.8, 1.4])
    with hdr_col1:
        st.markdown(
            f"""
            <div class="top-banner" style="margin-bottom:6px;">
                <div>
                    <h1>🎯 課堂即時搶答抽籤 × 全班座次計分系統</h1>
                    <p>目前班級：<b>{html.escape(active_cls_label)}</b>（已載入 {len(active_roster)} 位學生名單）</p>
                </div>
                <div class="status-pill">🔓 老師控制台</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hdr_col2:
        st.write("")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("🔑 密碼", use_container_width=True):
                st.session_state.show_passcode_settings = not st.session_state.show_passcode_settings
        with b2:
            if st.button("🔒 鎖定", use_container_width=True):
                st.session_state.admin_authenticated = False
                st.session_state.show_passcode_settings = False
                st.rerun()

    # 修改教師密碼面板（可展開/收合）
    if st.session_state.show_passcode_settings:
        with st.container(border=True):
            st.markdown("#### 🔑 修改教師端解鎖密碼")
            pc1, pc2, pc3 = st.columns([1.4, 1.4, 1])
            with pc1:
                new_pwd1 = st.text_input("輸入新密碼", type="password", placeholder="建議 4～12 碼數字或英文", key="new_pwd_1")
            with pc2:
                new_pwd2 = st.text_input("再次確認新密碼", type="password", placeholder="請再輸入一次新密碼", key="new_pwd_2")
            with pc3:
                st.write("")
                st.write("")
                if st.button("💾 儲存新密碼", type="primary", use_container_width=True):
                    if not new_pwd1.strip():
                        st.error("新密碼不可為空白！")
                    elif new_pwd1.strip() != new_pwd2.strip():
                        st.error("兩次輸入的密碼不一致！")
                    else:
                        with state["lock"]:
                            state["admin_passcode_hash"] = hash_passcode(new_pwd1.strip())
                            save_persisted_state(state)
                        st.session_state.show_passcode_settings = False
                        st.success("✅ 教師端密碼已成功更新！")
                        st.rerun()

    # 兩大主功能分頁切換
    tab_draw, tab_seating = st.tabs(["🎰 搶答抽籤主控台", "🗺️ 全班座次表記分（8×8 走道版）"])

    # ==========================================
    # 分頁一：搶答抽籤主控台
    # ==========================================
    with tab_draw:
        # 獨立於左右兩欄之外的輪轉音效佔位器，避免抽籤瞬間推移右側「今日即時記分板」
        rolling_sound_box = st.empty()
        left_col, right_col = st.columns([1.5, 1], gap="large")

        # --------------------------------------
        # 左側：問題流程控制 + 大螢幕中籤聚光燈 + 即時舉手名單
        # --------------------------------------
        with left_col:
            c_btn1, c_btn2, c_btn3 = st.columns([1.25, 1.15, 1])
            with c_btn1:
                if st.button("🆕 開啟下一題（清空舉手）", type="primary", use_container_width=True):
                    with state["lock"]:
                        state["round"] += 1
                        state["is_open"] = True
                        state["candidates"].clear()
                        state["last_winners"] = []
                        state["last_points_awarded"] = 0
                        save_persisted_state(state)
                    st.rerun()

            with c_btn2:
                toggle_label = "⏸️ 截止本題舉手" if state["is_open"] else "▶️ 恢復開放舉手"
                if st.button(toggle_label, use_container_width=True):
                    with state["lock"]:
                        state["is_open"] = not state["is_open"]
                        save_persisted_state(state)
                    st.rerun()

            with c_btn3:
                if st.button("🧹 清空本題名單", use_container_width=True):
                    with state["lock"]:
                        state["candidates"].clear()
                        state["last_winners"] = []
                        save_persisted_state(state)
                    st.rerun()

            # 中籤大螢幕聚光燈看板（固定總高度 224px 與內部卡片 138px，抽籤前後零跳動）
            spotlight_placeholder = st.empty()

            def render_spotlight_html(winners, pts_awarded, rolling=False):
                _, _, cur_roster, _ = get_active_roster_info()
                if rolling:
                    pills_html = ""
                    for idx, w in enumerate(winners, start=1):
                        stu_name = html.escape(cur_roster.get(w, {}).get("name", ""))
                        name_display = stu_name if stu_name else "抽籤中..."
                        pills_html += (
                            f'<div class="winner-pill rolling-pill">'
                            f'<div class="winner-pill-rank">🎲 輪轉中 #{idx}</div>'
                            f'<div class="winner-pill-num">{html.escape(w)}</div>'
                            f'<div class="winner-pill-footer">'
                            f'<div class="winner-pill-name">{name_display}</div>'
                            f'</div>'
                            f'</div>'
                        )
                    return (
                        f'<div class="winner-spotlight rolling">'
                        f'<div style="font-size:0.95rem; font-weight:800; color:#b45309;">🎰 正在隨機抽取發言同學...</div>'
                        f'<div class="winner-grid">{pills_html}</div>'
                        f'</div>'
                    )
                elif winners:
                    pills_html = ""
                    for idx, w in enumerate(winners, start=1):
                        stu_name = html.escape(cur_roster.get(w, {}).get("name", ""))
                        got_pts = f" +{pts_awarded}分" if pts_awarded > 0 else ""
                        sub_text = f"{stu_name}{got_pts}" if stu_name else (got_pts.strip() or "請準備發言")
                        pills_html += (
                            f'<div class="winner-pill">'
                            f'<div class="winner-pill-rank">🏆 第 {idx} 位中籤</div>'
                            f'<div class="winner-pill-num">{html.escape(w)}</div>'
                            f'<div class="winner-pill-footer">'
                            f'<div class="winner-pill-name">{sub_text}</div>'
                            f'</div>'
                            f'</div>'
                        )
                    return (
                        f'<div class="winner-spotlight">'
                        f'<div style="font-size:0.95rem; font-weight:800; color:#1d4ed8;">🎯 本題中籤發言同學（第 {state["round"]} 題）</div>'
                        f'<div class="winner-grid">{pills_html}</div>'
                        f'</div>'
                    )
                else:
                    return (
                        f'<div class="winner-spotlight empty">'
                        f'<div style="font-size:1.05rem; font-weight:700; color:#64748b;">等待學生掃碼舉手後，點擊右側「🎰 開始公平抽籤」</div>'
                        f'<div style="font-size:0.84rem; color:#94a3b8; margin-top:4px;">抽籤時將顯示滾動動畫並自動為中籤者加分</div>'
                        f'</div>'
                    )

            spotlight_placeholder.markdown(
                render_spotlight_html(state["last_winners"], state["last_points_awarded"], rolling=False),
                unsafe_allow_html=True,
            )

            # 即時舉手池監控面板（每 1.5 秒自動更新學生舉手狀態）
            @st.fragment(run_every=1.5)
            def live_pool_monitor():
                with state["lock"]:
                    cur_round = state["round"]
                    is_open = state["is_open"]
                    cand_items = list(state["candidates"].items())
                    hist = dict(state["history"])
                    _, _, cur_roster, _ = get_active_roster_info()

                status_txt = "🟢 開放舉手中" if is_open else "🔴 已截止舉手"
                st.markdown(
                    f'<div class="section-header">🙋 第 {cur_round} 題即時舉手名單（共 {len(cand_items)} 人｜{status_txt}）</div>',
                    unsafe_allow_html=True,
                )

                if not cand_items:
                    st.markdown(
                        '<div class="candidate-pool" style="justify-content:center; color:#94a3b8; font-weight:600;">尚無學生舉手，請學生掃描右側 QR Code 加入</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    badges_html = ""
                    for num, _ in cand_items:
                        spoken_times = hist.get(num, 0)
                        disp_label = html.escape(format_student_badge(num, cur_roster, include_class=False))
                        if spoken_times == 0:
                            badges_html += f'<div class="cand-badge boosted">{disp_label} <span class="tag">3x優先</span></div>'
                        else:
                            badges_html += f'<div class="cand-badge">{disp_label} <span style="font-size:0.75rem;color:#64748b;">(已發言{spoken_times}次)</span></div>'
                    st.markdown(f'<div class="candidate-pool">{badges_html}</div>', unsafe_allow_html=True)

            live_pool_monitor()

            # 手動補登座號（備用）
            with st.expander("⌨️ 老師手動補登座號（若個別學生手機沒電）"):
                with st.form("manual_add_form", clear_on_submit=True):
                    m_col1, m_col2 = st.columns([2.5, 1])
                    with m_col1:
                        manual_nums = st.text_input("輸入座號（可空格或逗號分隔多個，例如：03 15 28）", placeholder="例如：03 15")
                    with m_col2:
                        st.write("")
                        st.write("")
                        submitted_manual = st.form_submit_button("➕ 加入舉手池", use_container_width=True)
                    if submitted_manual and manual_nums.strip():
                        tokens = manual_nums.replace(",", " ").replace("、", " ").split()
                        added_list = []
                        with state["lock"]:
                            for t in tokens:
                                norm = normalize_seat_num(t)
                                if norm:
                                    state["candidates"][norm] = time.time()
                                    added_list.append(norm)
                            save_persisted_state(state)
                        if added_list:
                            st.toast(f"已手動加入座號：{', '.join(added_list)}")
                            st.rerun()

        # --------------------------------------
        # 右側：抽籤設定與啟動 + 即時記分板 + 學生端 QR Code
        # --------------------------------------
        with right_col:
            with st.container(border=True):
                st.markdown('<div class="section-header">🎲 抽籤規則與啟動</div>', unsafe_allow_html=True)

                set_c1, set_c2 = st.columns(2)
                with set_c1:
                    pick_count = st.number_input("本題抽取人數", min_value=1, max_value=10, value=1, step=1)
                with set_c2:
                    auto_points = st.number_input("中籤自動加分", min_value=0, max_value=10, value=1, step=1)

                opt_c1, opt_c2, opt_c3 = st.columns(3)
                with opt_c1:
                    fair_weight = st.checkbox("未發言3倍權重", value=True)
                with opt_c2:
                    auto_close = st.checkbox("抽籤後自動截止", value=True)
                with opt_c3:
                    sound_on = st.checkbox("開啟音效回饋", value=True, key="sound_on_toggle")

                if st.button("🎰 開始公平抽籤", type="primary", use_container_width=True):
                    with state["lock"]:
                        pool_snapshot = list(state["candidates"].keys())
                        hist_snapshot = dict(state["history"])

                    if not pool_snapshot:
                        st.warning("⚠️ 目前還沒有學生舉手喔！")
                    else:
                        actual_pick = min(int(pick_count), len(pool_snapshot))
                        with rolling_sound_box:
                            play_sound_effect("rolling", enabled=sound_on)

                        # 滾動揭曉動畫（約 0.9 秒）
                        for step in range(9):
                            fake_sample = random.sample(pool_snapshot, k=actual_pick)
                            spotlight_placeholder.markdown(
                                render_spotlight_html(fake_sample, 0, rolling=True),
                                unsafe_allow_html=True,
                            )
                            time.sleep(0.08 + step * 0.012)

                        # 正式加權抽籤
                        final_winners = pick_weighted_candidates(
                            pool_snapshot, hist_snapshot, count=actual_pick, weighted=fair_weight
                        )

                        with state["lock"]:
                            state["last_winners"] = final_winners
                            state["last_points_awarded"] = int(auto_points)
                            for w in final_winners:
                                state["history"][w] = state["history"].get(w, 0) + 1
                                if auto_points > 0:
                                    state["scores"][w] = state["scores"].get(w, 0) + int(auto_points)
                            if auto_close:
                                state["is_open"] = False
                            save_persisted_state(state)

                        st.session_state.play_fanfare_once = True
                        st.rerun()

            # 今日即時記分板
            with st.container(border=True):
                sb_h1, sb_h2 = st.columns([2, 1])
                with sb_h1:
                    st.markdown('<div class="section-header">🏆 今日即時記分板</div>', unsafe_allow_html=True)
                with sb_h2:
                    if st.button("🔄 重置今日分數", use_container_width=True):
                        with state["lock"]:
                            state["scores"].clear()
                            state["history"].clear()
                            state["last_winners"] = []
                            save_persisted_state(state)
                        st.rerun()

                @st.fragment(run_every=2.0)
                def live_scoreboard():
                    with state["lock"]:
                        score_items = sorted(state["scores"].items(), key=lambda x: (-x[1], x[0]))
                        hist_map = dict(state["history"])
                        _, _, cur_roster, _ = get_active_roster_info()

                    if not score_items:
                        st.caption("目前尚無得分紀錄，抽籤中籤或從「全班座次表」點擊加分即可累積！")
                    else:
                        top_list = score_items[:6]
                        for rank, (num, pts) in enumerate(top_list, start=1):
                            medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"#{rank}"))
                            top_cls = "top-rank" if rank <= 3 else ""
                            spoke = hist_map.get(num, 0)
                            disp_name = html.escape(format_student_badge(num, cur_roster, include_class=False))
                            st.markdown(
                                f'<div class="score-card {top_cls}">'
                                f'<div><span style="margin-right:6px;">{medal}</span><span class="score-num">{disp_name}</span> '
                                f'<span style="font-size:0.78rem; color:#64748b;">(發言{spoke}次)</span></div>'
                                f'<div class="score-pts">{pts} 分</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        if len(score_items) > 6:
                            st.caption(f"其餘 {len(score_items) - 6} 位同學得分可切換至「🗺️ 全班座次表記分」查看。")

                live_scoreboard()

            # 學生端 QR Code 分享卡片（已固定預設網址為 https://class-draw.streamlit.app/）
            with st.container(border=True):
                st.markdown('<div class="section-header">📱 學生手機掃碼加入</div>', unsafe_allow_html=True)
                qr_c1, qr_c2 = st.columns([1.15, 1.35])
                with qr_c1:
                    default_student_url = state.get("student_share_url", "https://class-draw.streamlit.app/")
                    student_url = st.text_input(
                        "學生端網址（免密碼）",
                        value=default_student_url,
                        help="學生掃描右側 QR Code 後直接進入學生端，看不到老師端密碼與後台。",
                    )
                    clean_student_url = student_url.split("?")[0].strip() if student_url else ""
                    if clean_student_url and clean_student_url != state.get("student_share_url"):
                        with state["lock"]:
                            state["student_share_url"] = clean_student_url
                            save_persisted_state(state)
                    st.caption("學生手機掃描 QR Code 後直接進入舉手畫面，無需輸入密碼。")
                with qr_c2:
                    if clean_student_url and HAS_QR:
                        qr_bytes = build_qr_image(clean_student_url)
                        if qr_bytes:
                            st.image(qr_bytes, width=148)
                    elif not HAS_QR:
                        st.info("安裝 `qrcode[pil]` 即可自動顯示 QR Code。")

        # 在最底部播放中獎音效，確保「抽籤主控台」與「中籤藍框框」之間零隱藏元素空隙
        if st.session_state.play_fanfare_once:
            st.session_state.play_fanfare_once = False
            play_sound_effect("fanfare", enabled=st.session_state.get("sound_on_toggle", True))

    # ==========================================
    # 分頁二：全班座次表記分（8×8 走道版 + 多週成績結算總表）
    # ==========================================
    with tab_seating:
        # 1. 三個班級名單快速切換列
        slot_c1, slot_c2, slot_c3 = st.columns(3)
        slot_buttons = [
            (slot_c1, "slot_1", "📘 班級一"),
            (slot_c2, "slot_2", "📗 班級二"),
            (slot_c3, "slot_3", "📙 班級三"),
        ]
        for col_obj, s_key, prefix in slot_buttons:
            with col_obj:
                s_info = state["rosters"].get(s_key, {"label": prefix, "students": {}, "dates": []})
                s_label = s_info.get("label", prefix)
                s_count = len(s_info.get("students", {}))
                is_active = (active_slot == s_key)
                btn_type = "primary" if is_active else "secondary"
                icon_mark = "✅ " if is_active else ""
                if st.button(f"{icon_mark}{s_label}（{s_count}人）", key=f"switch_{s_key}", type=btn_type, use_container_width=True):
                    with state["lock"]:
                        state["active_roster_slot"] = s_key
                        save_persisted_state(state)
                    st.rerun()

        # 2. 班級名單匯入、多週累計結算與總表匯出（預設收合，上課直接看座次表）
        with st.expander("📂 管理三個班級的 CSV 名單、結算今日成績與下載總表（支援學期累計）", expanded=False):
            # 頂部快速還原 GitHub 預設名單按鈕
            gh_c1, gh_c2 = st.columns([2.2, 1])
            with gh_c1:
                st.caption("💡 系統啟動時會自動偵測並載入 GitHub 倉庫中預存的 `default_rosters` 三個班級名單；若需手動重新載入預設名單可點擊右側按鈕。")
            with gh_c2:
                if st.button("🔄 從 GitHub 載入預設名單", use_container_width=True, key="reload_github_default_rosters"):
                    gh_defaults = load_default_rosters_from_github()
                    if gh_defaults:
                        with state["lock"]:
                            for sk, sdata in gh_defaults.items():
                                state["rosters"][sk] = sdata
                            save_persisted_state(state)
                        st.success(f"✅ 已從 GitHub 成功載入 {len(gh_defaults)} 個班級預設名單！")
                        st.rerun()
                    else:
                        st.warning("⚠️ 在 GitHub 倉庫中找不到 `default_rosters` 預設名單檔案。")

            st.divider()
            mgmt_c1, mgmt_c2, mgmt_c3 = st.columns([1.2, 1.45, 1.35])

            with mgmt_c1:
                st.markdown("**① 下載空白範本 / 學期總表**")
                st.download_button(
                    label="📄 下載空白名單範本",
                    data=generate_template_csv(),
                    file_name="班級座次名單範本.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
                gradebook_csv_bytes = generate_gradebook_csv(active_slot)
                today_fn = datetime.now().strftime("%Y%m%d")
                st.download_button(
                    label=f"📊 下載學期累計總表 ({len(active_dates)}週)",
                    data=gradebook_csv_bytes,
                    file_name=f"{active_cls_label}_學期累計成績總表_{today_fn}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            with mgmt_c2:
                st.markdown("**② 匯入名單或上週累計總表 (.csv)**")
                slot_idx_map = {"slot_1": "班級 1", "slot_2": "班級 2", "slot_3": "班級 3"}
                target_slot = st.selectbox(
                    "選擇要匯入的班級位置",
                    options=["slot_1", "slot_2", "slot_3"],
                    index=["slot_1", "slot_2", "slot_3"].index(active_slot) if active_slot in slot_idx_map else 0,
                    format_func=lambda k: (
                        f"{state['rosters'].get(k, {}).get('label', slot_idx_map.get(k, k))}"
                        f"（目前 {len(state['rosters'].get(k, {}).get('students', {}))} 人）"
                    ),
                )
                uploaded_csv = st.file_uploader(
                    "上傳 CSV（可匯入新名單或先前下載的累計總表）",
                    type=["csv"],
                    key="roster_csv_uploader",
                )
                if uploaded_csv is not None:
                    parsed_students, parsed_dates, parsed_label = parse_csv_roster(uploaded_csv.getvalue())
                    if not parsed_students:
                        st.error("❌ 無法從 CSV 讀取有效座號與姓名，請確認包含「班級、座號、姓名」欄位。")
                    else:
                        date_note = f"、內含 **{len(parsed_dates)} 次**歷史成績欄位" if parsed_dates else ""
                        st.info(f"偵測到 **{parsed_label}**，共 **{len(parsed_students)} 位**學生{date_note}。")
                        if st.button("✅ 確認匯入並覆蓋此班級", type="primary", use_container_width=True):
                            with state["lock"]:
                                state["rosters"][target_slot] = {
                                    "label": parsed_label,
                                    "students": parsed_students,
                                    "dates": parsed_dates,
                                }
                                state["active_roster_slot"] = target_slot
                                save_persisted_state(state)
                            st.success(f"🎉 已成功匯入「{parsed_label}」！")
                            st.rerun()

            with mgmt_c3:
                st.markdown("**③ 下課結算今日成績寫入總表**")
                default_today_str = datetime.now().strftime("%Y/%m/%d")
                settle_date_str = st.text_input(
                    "本次上課日期欄位名稱",
                    value=default_today_str,
                    placeholder="例如：2026/11/23",
                    help="系統會將今日所有同學得分寫入此日期欄位，並自動加總「學期總加分」。",
                )
                reset_after_settle = st.checkbox("寫入總表後自動歸零今日暫存分數", value=True)
                if st.button("💾 結算今日寫入總表", type="primary", use_container_width=True):
                    ok, msg = settle_today_scores_to_roster(active_slot, settle_date_str, reset_today=reset_after_settle)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        # 3. 講台指示條（教師視角：從講台往後看教室 8 行 × 8 列，每2人一排中間有走道）
        st.markdown(
            f'<div class="podium-bar">🖥️ 講台方向（教師視角：第 01～08 號為最前排 ｜ 每 2 位同學一排，中間為教室走道 ｜ 已累計 {len(active_dates)} 次上課成績）</div>',
            unsafe_allow_html=True,
        )

        # 4. 繪製 8 列 × 8 行（共 64 格）座次表，第 2-3、4-5、6-7 行之間加入縱向走道分隔線
        # 欄位比例：[1, 1, 走道0.22, 1, 1, 走道0.22, 1, 1, 走道0.22, 1, 1]
        col_ratios = [1, 1, 0.22, 1, 1, 0.22, 1, 1, 0.22, 1, 1]
        aisle_col_indices = {2, 5, 8}
        seat_col_map = [0, 1, 3, 4, 6, 7, 9, 10]

        recent_winners_set = set(state.get("last_winners", []))

        for row_idx in range(8):
            grid_cols = st.columns(col_ratios, gap="small")

            # 在第 2-3、4-5、6-7 行之間繪製走道視覺分隔
            for aisle_idx in aisle_col_indices:
                with grid_cols[aisle_idx]:
                    aisle_tag = "走道" if row_idx in (1, 4, 7) else ""
                    label_html = f'<div class="aisle-label">{aisle_tag}</div>' if aisle_tag else ""
                    st.markdown(f'<div class="aisle-divider">{label_html}</div>', unsafe_allow_html=True)

            # 繪製該橫排 8 個座位（座號順序：由講台往後看，第1排左到右為 01~08，第2排為 09~16...）
            for seat_c_idx in range(8):
                seat_int = row_idx * 8 + seat_c_idx + 1
                seat_str = f"{seat_int:02d}"
                stu_info = active_roster.get(seat_str)
                cur_pts = state["scores"].get(seat_str, 0)

                with grid_cols[seat_col_map[seat_c_idx]]:
                    if stu_info:
                        stu_name = html.escape(stu_info.get("name", ""))
                        stu_cls = html.escape(stu_info.get("class_name", ""))
                        sem_total = int(stu_info.get("semester_total", 0))
                        card_classes = ["seat-card"]
                        if cur_pts >= 3:
                            card_classes.append("high-score")
                        elif cur_pts > 0:
                            card_classes.append("has-score")
                        if seat_str in recent_winners_set:
                            card_classes.append("recent-winner")

                        pill_cls = "seat-score-pill" if cur_pts != 0 else "seat-score-pill zero"
                        sem_hint = f" · 總{sem_total}" if (sem_total > 0 or active_dates) else ""
                        st.markdown(
                            f'<div class="{" ".join(card_classes)}">'
                            f'<div class="seat-top-row"><span>{seat_str}</span><span class="{pill_cls}">{cur_pts}分</span></div>'
                            f'<div class="seat-name" title="{stu_name}">{stu_name}</div>'
                            f'<div class="seat-class-tag">{stu_cls}{sem_hint}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        # 緊湊加減分按鈕（直接修改 scores 並觸發音效、震動與連點浮動氣泡）
                        b_add, b_sub = st.columns(2, gap="small")
                        with b_add:
                            if st.button(
                                "➕",
                                key=f"seat_add_{active_slot}_{seat_str}",
                                use_container_width=True,
                            ):
                                adjust_seat_score(seat_str, 1)
                                st.rerun()
                        with b_sub:
                            if st.button(
                                "➖",
                                key=f"seat_sub_{active_slot}_{seat_str}",
                                use_container_width=True,
                            ):
                                adjust_seat_score(seat_str, -1)
                                st.rerun()
                    else:
                        # 空座位卡片
                        st.markdown(
                            f'<div class="seat-card empty-seat">'
                            f'<div class="seat-top-row"><span>{seat_str}</span><span class="seat-score-pill zero">-</span></div>'
                            f'<div class="seat-name" style="color:#94a3b8; font-weight:600;">(空位)</div>'
                            f'<div class="seat-class-tag">&nbsp;</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )