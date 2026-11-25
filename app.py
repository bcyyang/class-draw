# ... existing code ...
            # 若學生已確認綁定座號，頂部顯示個人今日分數與學期總加分看板
            saved_seat = st.session_state.student_saved_num
            confirmed_seat = st.session_state.student_confirmed_seat
            if saved_seat and confirmed_seat == saved_seat:
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
                        cls_prefix = f"{stu_cls} · " if stu_cls else ""
                        confirm_html = (
                            f'<div style="background:#fffbeb; border:2px solid #f59e0b; border-radius:14px; padding:14px 16px; margin-bottom:10px; text-align:center;">'
                            f'<div style="font-size:0.84rem; font-weight:800; color:#b45309;">🔍 請確認你的身分</div>'
                            f'<div style="font-size:1.35rem; font-weight:900; color:#0f172a; margin-top:4px;">{cls_prefix}{clean_seat} 號 · {stu_name}</div>'
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