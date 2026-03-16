import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import uuid

# ==========================================
# 💡 設定
# ==========================================
GAS_URL = "https://script.google.com/macros/s/★★ここを書き換える★★/exec"

st.set_page_config(page_title="子ども食堂 リマインド管理", page_icon="🍛", layout="centered")

st.markdown("""
    <style>
    .main-title { color: #E67E22; text-align: center; font-family: 'Helvetica Neue', Arial, sans-serif; }
    .stButton>button { background-color: #E67E22; color: white; border-radius: 8px; width: 100%; font-weight: bold; }
    .stButton>button:hover { background-color: #D35400; color: white; }
    </style>
    <h1 class="main-title">🍛 子ども食堂 リマインド管理</h1>
    <hr>
""", unsafe_allow_html=True)

JST = timezone(timedelta(hours=+9), 'JST')

def fetch_from_gas(action, payload=None):
    data = {"action": action}
    if payload: data["payload"] = payload
    try:
        response = requests.post(GAS_URL, json=data)
        result = response.json()
        if result.get("status") == "success": return result.get("data")
        else:
            st.error(f"GASエラー: {result.get('message')}")
            return None
    except Exception as e:
        st.error(f"通信エラー: {e}")
        return None

# ==========================================
# 💡 データの事前取得
# ==========================================
groups_data = fetch_from_gas("get_groups") or []
templates_data = fetch_from_gas("get_templates") or []
reminders_data = fetch_from_gas("get_reminders") or []

group_dict = {f"{g['group_name']}": g['group_id'] for g in groups_data}
group_rev_dict = {v: k for k, v in group_dict.items()} # IDから名前を引く用

# タブの作成
tab1, tab2, tab3 = st.tabs(["📅 リマインド予約", "📋 一覧・編集", "⚙️ 設定 (グループ・テンプレート)"])

# ==========================================
# タブ1：リマインド予約
# ==========================================
with tab1:
    st.subheader("新しいリマインドを予約")
    
    if not group_dict:
        st.warning("⚠️ グループが登録されていません。「設定」タブを確認してください。")
    else:
        # テンプレート選択（フォームの外に置くことでリアルタイム反映させる）
        template_options = ["(テンプレートを使用しない)"] + [t['name'] for t in templates_data]
        selected_template_name = st.selectbox("📝 テンプレートを読み込む", template_options)
        
        default_message = ""
        if selected_template_name != "(テンプレートを使用しない)":
            default_message = next(t['content'] for t in templates_data if t['name'] == selected_template_name)

        with st.form("reminder_form", clear_on_submit=True):
            selected_group_label = st.selectbox("送信先LINEグループ", options=list(group_dict.keys()))
            
            col1, col2 = st.columns(2)
            with col1: send_date = st.date_input("送信日", value=datetime.now(JST) + timedelta(days=1))
            with col2: send_time = st.time_input("送信時間", value=datetime.strptime("17:00", "%H:%M").time())
            
            # テンプレートが選ばれたら初期値にセットされる
            message_text = st.text_area("メッセージ内容", value=default_message, height=150)
            
            if st.form_submit_button("予約する"):
                if not message_text.strip():
                    st.error("メッセージ内容を入力してください。")
                else:
                    dt_str = f"{send_date.strftime('%Y/%m/%d')} {send_time.strftime('%H:%M:00')}"
                    payload = {
                        "id": "RM-" + str(uuid.uuid4())[:8],
                        "send_time": dt_str,
                        "message": message_text,
                        "target_group_id": group_dict[selected_group_label]
                    }
                    if fetch_from_gas("add_reminder", payload) == "success":
                        st.success("✅ 予約しました！")
                        st.rerun() # 画面をリロードして一覧を更新

# ==========================================
# タブ2：予約一覧・編集
# ==========================================
with tab2:
    st.subheader("予約済みのリマインド")
    if reminders_data:
        # 未送信のものだけを編集対象としてリストアップ
        pending_reminders = [r for r in reminders_data if r['status'] == '']
        
        if pending_reminders:
            st.write("▼ 編集または削除したいリマインドを選択してください")
            edit_options = { f"{r['send_time']} - {r['message'][:10]}...": r for r in pending_reminders }
            selected_edit_label = st.selectbox("対象の予約", list(edit_options.keys()))
            target_r = edit_options[selected_edit_label]
            
            # 編集フォーム
            with st.expander("✏️ 選択した予約を編集・削除", expanded=True):
                e_date_str, e_time_str = target_r['send_time'].split(" ")
                e_date = datetime.strptime(e_date_str, "%Y/%m/%d").date()
                e_time = datetime.strptime(e_time_str, "%H:%M:%S").time()
                
                # 現在のグループ名を取得（取得できない場合はリストの最初）
                current_g_name = group_rev_dict.get(target_r['target_group_id'], list(group_dict.keys())[0])
                
                new_group = st.selectbox("送信先", list(group_dict.keys()), index=list(group_dict.keys()).index(current_g_name), key="e_group")
                c1, c2 = st.columns(2)
                with c1: new_date = st.date_input("送信日", value=e_date, key="e_date")
                with c2: new_time = st.time_input("送信時間", value=e_time, key="e_time")
                new_message = st.text_area("メッセージ", value=target_r['message'], height=100, key="e_msg")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("更新する", type="primary"):
                        new_dt_str = f"{new_date.strftime('%Y/%m/%d')} {new_time.strftime('%H:%M:00')}"
                        payload = {"id": target_r['id'], "send_time": new_dt_str, "message": new_message, "target_group_id": group_dict[new_group]}
                        if fetch_from_gas("update_reminder", payload) == "success":
                            st.success("更新しました！")
                            st.rerun()
                with col_btn2:
                    if st.button("🗑️ この予約を削除"):
                        if fetch_from_gas("delete_reminder", {"id": target_r['id']}) == "success":
                            st.warning("削除しました。")
                            st.rerun()

        # 一覧表の表示
        st.markdown("---")
        df = pd.DataFrame(reminders_data)
        df['group_name'] = df['target_group_id'].map(group_rev_dict).fillna("不明")
        display_df = df[['send_time', 'group_name', 'message', 'status']].copy()
        display_df.rename(columns={'send_time': '日時', 'group_name': '送信先', 'message': 'メッセージ', 'status': '状態'}, inplace=True)
        display_df['状態'] = display_df['状態'].replace({'': '⏳ 待機中', 'DONE': '✅ 送信済', 'ERROR': '❌ エラー'})
        st.dataframe(display_df.sort_values(by='日時', ascending=False).reset_index(drop=True), use_container_width=True)
    else:
        st.info("現在予約されているリマインドはありません。")

# ==========================================
# タブ3：設定 (グループ・テンプレート)
# ==========================================
with tab3:
    st.subheader("LINEグループ名の変更")
    st.caption("ボットが参加しているグループに分かりやすい名前を付けます。")
    if groups_data:
        edit_group_target = st.selectbox("名前を変更するグループを選択", [g['group_name'] for g in groups_data])
        target_g_id = group_dict[edit_group_target]
        new_g_name = st.text_input("新しい名前を入力", value=edit_group_target)
        if st.button("グループ名を更新"):
            if fetch_from_gas("update_group", {"group_id": target_g_id, "group_name": new_g_name}) == "success":
                st.success("グループ名を更新しました！")
                st.rerun()
    else:
        st.write("グループがありません。ボットをLINEグループに招待してください。")

    st.markdown("---")
    
    st.subheader("メッセージテンプレート管理")
    with st.expander("➕ 新しいテンプレートを作成"):
        t_name = st.text_input("テンプレート名 (例: 通常開催用)")
        t_content = st.text_area("メッセージ内容", height=100)
        if st.button("テンプレートを保存"):
            if t_name and t_content:
                payload = {"id": "TPL-" + str(uuid.uuid4())[:8], "name": t_name, "content": t_content}
                if fetch_from_gas("save_template", payload) == "success":
                    st.success("保存しました！")
                    st.rerun()
            else:
                st.error("名前と内容の両方を入力してください。")
                
    if templates_data:
        st.write("▼ 登録済みのテンプレート")
        for t in templates_data:
            col_t1, col_t2 = st.columns([4, 1])
            with col_t1:
                st.write(f"**{t['name']}**")
                st.caption(f"{t['content'][:20]}...")
            with col_t2:
                if st.button("削除", key=f"del_{t['id']}"):
                    if fetch_from_gas("delete_template", {"id": t['id']}) == "success":
                        st.rerun()
