import sqlite3
from pathlib import Path
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st
import os

DB_FILE = Path(__file__).with_name("finance_manager.db")
CATEGORIES = ["飲食", "交通", "娛樂", "購物", "學習", "住宿", "其他"]
INCOME_CATEGORIES = ["薪資", "零用錢", "投資", "其他"]


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def execute_sql(sql, params=()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    conn.close()


def fetch_df(sql, params=()):
    conn = get_connection()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_month_string():
    return date.today().strftime("%Y-%m")


def format_money(value):
    try:
        return f"＄{float(value):,.0f}"
    except Exception:
        return "＄0"


def money_card(title, value):
    st.markdown(
        f"""
        <div class="money-card">
            <div class="money-title">{title}</div>
            <div class="money-value" translate="no">{format_money(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def percent_card(title, value):
    st.markdown(
        f"""
        <div class="money-card">
            <div class="money-title">{title}</div>
            <div class="money-value" translate="no">{value:.1f}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            t_date TEXT NOT NULL,
            t_type TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS budgets (
            month TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (month, category)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY,
            name TEXT,
            monthly_income REAL DEFAULT 0,
            finance_goal TEXT,
            emergency_months INTEGER DEFAULT 3,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS saving_goal (
            id INTEGER PRIMARY KEY,
            goal_name TEXT,
            target_amount REAL DEFAULT 0,
            current_amount REAL DEFAULT 0,
            deadline TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def ensure_month_budgets(month):
    for category in CATEGORIES:
        execute_sql(
            "INSERT OR IGNORE INTO budgets (month, category, amount) VALUES (?, ?, 0)",
            (month, category),
        )


def get_month_transactions(month):
    return fetch_df(
        """
        SELECT id, t_date, t_type, category, amount, note, created_at
        FROM transactions
        WHERE substr(t_date, 1, 7) = ?
        ORDER BY t_date DESC, id DESC
        """,
        (month,),
    )


def get_all_transactions():
    return fetch_df(
        """
        SELECT id, t_date, t_type, category, amount, note, created_at
        FROM transactions
        ORDER BY t_date ASC, id ASC
        """
    )


def get_month_budgets(month):
    ensure_month_budgets(month)
    return fetch_df(
        """
        SELECT category, amount
        FROM budgets
        WHERE month = ?
        ORDER BY CASE category
            WHEN '飲食' THEN 1
            WHEN '交通' THEN 2
            WHEN '娛樂' THEN 3
            WHEN '購物' THEN 4
            WHEN '學習' THEN 5
            WHEN '住宿' THEN 6
            ELSE 7
        END
        """,
        (month,),
    )


def get_profile():
    df = fetch_df("SELECT * FROM profile WHERE id = 1")
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_goal():
    df = fetch_df("SELECT * FROM saving_goal WHERE id = 1")
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def apply_style():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 3rem; }
        h1 { font-size: 44px !important; font-weight: 800 !important; color: #1f2937 !important; }
        h2, h3 { color: #1f2937 !important; font-weight: 700 !important; }
        .money-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 24px 22px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.04);
            min-height: 120px;
            margin-bottom: 12px;
        }
        .money-title {
            font-size: 18px;
            font-weight: 600;
            color: #111827;
            margin-bottom: 16px;
        }
        .money-value {
            font-size: 36px;
            font-weight: 700;
            color: #1f2937;
            white-space: nowrap;
        }
        .quick-card {
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 10px;
            font-size: 16px;
            color: #1f2937;
        }
        .small-title {
            font-size: 24px;
            font-weight: 700;
            color: #1f2937;
            margin: 8px 0 16px 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def add_transaction_box():
    st.markdown("<div class='small-title'>新增一筆收支</div>", unsafe_allow_html=True)

    # 類型放在 form 外面，這樣點收入/支出時會立即更新分類
    t_type = st.radio(
        "類型",
        ["支出", "收入"],
        horizontal=True,
        key="quick_add_type"
    )

    categories = CATEGORIES if t_type == "支出" else INCOME_CATEGORIES

    with st.form("add_transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            t_date = st.date_input("日期", value=date.today())

        with col2:
            category = st.selectbox(
                "分類",
                categories,
                key=f"quick_add_category_{t_type}"
            )
            amount = st.number_input("金額", min_value=0, step=10)

        note = st.text_input("備註", placeholder="例如：午餐、捷運、書籍、薪水")

        submitted = st.form_submit_button("新增紀錄", use_container_width=True)

        if submitted:
            if amount <= 0:
                st.warning("金額要大於 0")
            else:
                execute_sql(
                    """
                    INSERT INTO transactions (t_date, t_type, category, amount, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        t_date.strftime("%Y-%m-%d"),
                        t_type,
                        category,
                        amount,
                        note,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
                st.success("已新增一筆紀錄")
                st.rerun()


def transaction_records_page(trans_df):
    if trans_df.empty:
        st.info("這個月份還沒有任何收支紀錄。")
        return
    show_df = trans_df.copy()
    show_df["amount"] = show_df["amount"].apply(format_money)
    show_df = show_df.rename(
        columns={
            "id": "編號",
            "t_date": "日期",
            "t_type": "類型",
            "category": "分類",
            "amount": "金額",
            "note": "備註",
            "created_at": "建立時間",
        }
    )
    st.dataframe(show_df, use_container_width=True, hide_index=True)
    st.divider()
    st.markdown("<div class='small-title'>編輯 / 刪除紀錄</div>", unsafe_allow_html=True)
    record_options = {
        f"{row['id']}｜{row['t_date']}｜{row['t_type']}｜{row['category']}｜{format_money(row['amount'])}": row["id"]
        for _, row in trans_df.iterrows()
    }
    selected_label = st.selectbox("選擇一筆紀錄", list(record_options.keys()))
    selected_id = record_options[selected_label]
    selected_row = trans_df[trans_df["id"] == selected_id].iloc[0]
    with st.form("edit_transaction_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_date = st.date_input("日期", value=datetime.strptime(selected_row["t_date"], "%Y-%m-%d").date())
            new_type = st.radio("類型", ["支出", "收入"], index=0 if selected_row["t_type"] == "支出" else 1, horizontal=True)
        with col2:
            categories = CATEGORIES if new_type == "支出" else INCOME_CATEGORIES
            current_category = selected_row["category"] if selected_row["category"] in categories else categories[0]
            new_category = st.selectbox("分類", categories, index=categories.index(current_category))
            new_amount = st.number_input("金額", min_value=0, step=10, value=int(selected_row["amount"]))
        new_note = st.text_input("備註", value="" if pd.isna(selected_row["note"]) else selected_row["note"])
        col_save, col_delete = st.columns(2)
        save_clicked = col_save.form_submit_button("儲存修改", use_container_width=True)
        delete_clicked = col_delete.form_submit_button("刪除這筆", use_container_width=True)
        if save_clicked:
            execute_sql(
                "UPDATE transactions SET t_date=?, t_type=?, category=?, amount=?, note=? WHERE id=?",
                (new_date.strftime("%Y-%m-%d"), new_type, new_category, new_amount, new_note, selected_id),
            )
            st.success("紀錄已更新")
            st.rerun()
        if delete_clicked:
            execute_sql("DELETE FROM transactions WHERE id=?", (selected_id,))
            st.success("紀錄已刪除")
            st.rerun()


def budget_page(selected_month, trans_df):
    budget_df = get_month_budgets(selected_month)
    st.markdown("<div class='small-title'>類別預算設定</div>", unsafe_allow_html=True)
    edited = st.data_editor(
        budget_df,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "category": st.column_config.TextColumn("分類", disabled=True),
            "amount": st.column_config.NumberColumn("預算金額", min_value=0, step=500),
        },
        key=f"budget_page_editor_{selected_month}",
    )
    if st.button("儲存預算", use_container_width=True):
        for _, row in edited.iterrows():
            execute_sql(
                """
                INSERT INTO budgets (month, category, amount)
                VALUES (?, ?, ?)
                ON CONFLICT(month, category) DO UPDATE SET amount = excluded.amount
                """,
                (selected_month, row["category"], float(row["amount"])),
            )
        st.success("預算已儲存")
        st.rerun()
    st.divider()
    st.markdown("<div class='small-title'>預算使用狀況</div>", unsafe_allow_html=True)
    expense_df = trans_df[trans_df["t_type"] == "支出"] if not trans_df.empty else pd.DataFrame()
    if expense_df.empty:
        st.info("這個月份還沒有支出資料。")
        return
    expense_by_cat = expense_df.groupby("category", as_index=False)["amount"].sum()
    report = edited.rename(columns={"amount": "budget"}).merge(
        expense_by_cat.rename(columns={"amount": "spent"}), on="category", how="left"
    ).fillna(0)
    for _, row in report.iterrows():
        budget = float(row["budget"])
        spent = float(row["spent"])
        usage_rate = spent / budget * 100 if budget > 0 else 0
        st.write(f"{row['category']}：{format_money(spent)} / {format_money(budget)}（{usage_rate:.1f}%）")
        if budget > 0:
            st.progress(min(usage_rate / 100, 1.0))
        if budget > 0 and spent > budget:
            st.error(f"{row['category']} 已經超支")


def analysis_charts(trans_df):
    expense_df = trans_df[trans_df["t_type"] == "支出"] if not trans_df.empty else pd.DataFrame()
    if expense_df.empty:
        st.info("這個月份還沒有支出資料，新增幾筆支出後就會產生圖表。")
        return
    category_sum = expense_df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 分類圓餅圖")
        fig1 = px.pie(category_sum, names="category", values="amount")
        fig1.update_traces(textposition="inside", textinfo="percent+label")
        fig1.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=420,
            font=dict(family="Microsoft JhengHei, Noto Sans CJK TC, Arial", size=14),
        )
        st.plotly_chart(fig1, use_container_width=True)
    with col2:
        st.markdown("### 分類支出排行")
        fig2 = px.bar(category_sum, x="category", y="amount", text="amount", labels={"category": "分類", "amount": "金額"})
        fig2.update_traces(texttemplate="%{text:.0f}", textposition="outside")
        fig2.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=420,
            font=dict(family="Microsoft JhengHei, Noto Sans CJK TC, Arial", size=14),
            xaxis_title="分類",
            yaxis_title="金額",
        )
        st.plotly_chart(fig2, use_container_width=True)
    all_df = get_all_transactions()
    if not all_df.empty:
        all_df["month"] = pd.to_datetime(all_df["t_date"]).dt.strftime("%Y-%m")
        trend = all_df[all_df["t_type"] == "支出"].groupby("month", as_index=False)["amount"].sum()
        if len(trend) >= 2:
            st.divider()
            st.markdown("### 每月支出趨勢")
            fig3 = px.line(trend, x="month", y="amount", markers=True, labels={"month": "月份", "amount": "支出"})
            fig3.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                height=360,
                font=dict(family="Microsoft JhengHei, Noto Sans CJK TC, Arial", size=14),
                xaxis_title="月份",
                yaxis_title="支出",
            )
            st.plotly_chart(fig3, use_container_width=True)


def saving_goal_page():
    goal = get_goal()
    with st.form("saving_goal_form"):
        goal_name = st.text_input("目標名稱", value="" if goal is None else goal.get("goal_name", ""))
        target_amount = st.number_input("目標金額", min_value=0.0, step=1000.0, value=0.0 if goal is None else float(goal.get("target_amount", 0) or 0))
        current_amount = st.number_input("目前已存", min_value=0.0, step=1000.0, value=0.0 if goal is None else float(goal.get("current_amount", 0) or 0))
        deadline_value = date.today() if goal is None or not goal.get("deadline") else datetime.strptime(goal.get("deadline"), "%Y-%m-%d").date()
        deadline = st.date_input("完成期限", value=deadline_value)
        submitted = st.form_submit_button("儲存儲蓄目標", use_container_width=True)
        if submitted:
            execute_sql(
                "INSERT OR REPLACE INTO saving_goal (id, goal_name, target_amount, current_amount, deadline) VALUES (1, ?, ?, ?, ?)",
                (goal_name, target_amount, current_amount, deadline.strftime("%Y-%m-%d")),
            )
            st.success("儲蓄目標已儲存")
            st.rerun()
    goal = get_goal()
    if goal is not None and float(goal.get("target_amount", 0) or 0) > 0:
        target = float(goal.get("target_amount", 0) or 0)
        current = float(goal.get("current_amount", 0) or 0)
        remaining = max(target - current, 0)
        progress = min(current / target, 1.0)
        deadline_date = datetime.strptime(goal.get("deadline"), "%Y-%m-%d").date()
        months_left = max((deadline_date.year - date.today().year) * 12 + deadline_date.month - date.today().month, 1)
        monthly_need = remaining / months_left
        st.divider()
        st.markdown("<div class='small-title'>儲蓄進度</div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            money_card("目標金額", target)
        with col2:
            money_card("目前已存", current)
        with col3:
            money_card("每月應存", monthly_need)
        st.progress(progress)
        st.write(f"目前進度：{progress * 100:.1f}%")
        st.write(f"剩餘金額：{format_money(remaining)}")


def profile_page():
    profile = get_profile()
    with st.form("profile_form"):
        name = st.text_input("姓名", value="" if profile is None else profile.get("name", ""))
        monthly_income = st.number_input("每月收入", min_value=0.0, step=1000.0, value=0.0 if profile is None else float(profile.get("monthly_income", 0) or 0))
        finance_goal = st.text_area("理財目標", value="" if profile is None else profile.get("finance_goal", ""))
        emergency_months = st.number_input("緊急預備金月數", min_value=1, max_value=12, value=3 if profile is None else int(profile.get("emergency_months", 3) or 3))
        submitted = st.form_submit_button("儲存使用者資料", use_container_width=True)
        if submitted:
            execute_sql(
                "INSERT OR REPLACE INTO profile (id, name, monthly_income, finance_goal, emergency_months, created_at) VALUES (1, ?, ?, ?, ?, ?)",
                (name, monthly_income, finance_goal, emergency_months, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            st.success("使用者資料已儲存")
            st.rerun()
    profile = get_profile()
    if profile is not None:
        st.divider()
        st.markdown("<div class='small-title'>目前資料</div>", unsafe_allow_html=True)
        st.write(f"姓名：{profile.get('name', '')}")
        st.write(f"每月收入：{format_money(profile.get('monthly_income', 0))}")
        st.write(f"理財目標：{profile.get('finance_goal', '')}")
        st.write(f"緊急預備金月數：{profile.get('emergency_months', 3)} 個月")


def generate_ai_suggestions(selected_month, trans_df, budget_df, profile, goal):
    suggestions = []
    if trans_df.empty:
        return ["目前還沒有收支資料，可以先新增幾筆收入與支出，系統才會開始分析。", "建議先設定每月預算與儲蓄目標，這樣 AI 理財建議會更準確。"]
    income = trans_df[trans_df["t_type"] == "收入"]["amount"].sum()
    expense = trans_df[trans_df["t_type"] == "支出"]["amount"].sum()
    balance = income - expense
    if income == 0:
        suggestions.append("本月尚未記錄收入，建議先新增收入資料，才能正確判斷收支狀況。")
    if expense > income and income > 0:
        suggestions.append("本月支出已經超過收入，建議先檢查娛樂、購物或飲食支出。")
    if balance > 0:
        suggestions.append(f"本月目前還有結餘 {format_money(balance)}，可以考慮投入儲蓄目標。")
    elif balance < 0:
        suggestions.append(f"本月目前超支 {format_money(abs(balance))}，建議下週降低非必要消費。")
    expense_df = trans_df[trans_df["t_type"] == "支出"]
    if not expense_df.empty:
        total_expense = expense_df["amount"].sum()
        category_sum = expense_df.groupby("category")["amount"].sum().sort_values(ascending=False)
        top_category = category_sum.index[0]
        top_amount = category_sum.iloc[0]
        top_rate = top_amount / total_expense * 100
        suggestions.append(f"本月最高支出分類是「{top_category}」，金額為 {format_money(top_amount)}，占總支出 {top_rate:.1f}%。")
        if top_category == "飲食" and top_rate >= 35:
            suggestions.append("飲食支出占比偏高，可以減少外送、飲料或非必要聚餐。")
        if top_category == "娛樂" and top_rate >= 30:
            suggestions.append("娛樂支出占比偏高，建議先設定娛樂預算上限。")
        if top_category == "購物" and top_rate >= 30:
            suggestions.append("購物支出占比偏高，建議購買前先延遲一天再決定。")
    if not budget_df.empty and not expense_df.empty:
        expense_by_cat = expense_df.groupby("category", as_index=False)["amount"].sum()
        report = budget_df.rename(columns={"amount": "budget"}).merge(expense_by_cat.rename(columns={"amount": "spent"}), on="category", how="left").fillna(0)
        for _, row in report.iterrows():
            budget = float(row["budget"])
            spent = float(row["spent"])
            if budget > 0 and spent > budget:
                suggestions.append(f"「{row['category']}」已經超出預算，預算是 {format_money(budget)}，目前已花 {format_money(spent)}。")
            elif budget > 0 and spent / budget >= 0.8:
                suggestions.append(f"「{row['category']}」預算已使用超過 80%，接下來要稍微控制。")
    if profile is not None:
        monthly_income = float(profile.get("monthly_income", 0) or 0)
        emergency_months = int(profile.get("emergency_months", 3) or 3)
        if monthly_income > 0:
            emergency_target = monthly_income * emergency_months
            suggestions.append(f"依照你設定的每月收入，建議至少準備 {format_money(emergency_target)} 作為緊急預備金。")
    if goal is not None and float(goal.get("target_amount", 0) or 0) > 0:
        target = float(goal.get("target_amount", 0) or 0)
        current = float(goal.get("current_amount", 0) or 0)
        remaining = max(target - current, 0)
        if remaining <= 0:
            suggestions.append("你的儲蓄目標已經達成，可以設定下一個理財目標。")
        else:
            deadline_date = datetime.strptime(goal.get("deadline"), "%Y-%m-%d").date()
            months_left = max((deadline_date.year - date.today().year) * 12 + deadline_date.month - date.today().month, 1)
            monthly_need = remaining / months_left
            suggestions.append(f"距離儲蓄目標還差 {format_money(remaining)}，若要如期完成，每月約需存 {format_money(monthly_need)}。")
    return suggestions if suggestions else ["目前財務狀況看起來穩定，可以持續記錄收支並維持預算控制。"]


def build_excel_report(selected_month, trans_df, budget_df, goal):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if trans_df.empty:
            pd.DataFrame(columns=["日期", "類型", "分類", "金額", "備註"]).to_excel(writer, sheet_name="每月收支表", index=False)
        else:
            report_df = trans_df[["t_date", "t_type", "category", "amount", "note"]].copy()
            report_df = report_df.rename(columns={"t_date": "日期", "t_type": "類型", "category": "分類", "amount": "金額", "note": "備註"})
            report_df.to_excel(writer, sheet_name="每月收支表", index=False)
        expense_df = trans_df[trans_df["t_type"] == "支出"] if not trans_df.empty else pd.DataFrame()
        if not expense_df.empty:
            category_report = expense_df.groupby("category", as_index=False)["amount"].sum().rename(columns={"category": "分類", "amount": "支出金額"})
        else:
            category_report = pd.DataFrame(columns=["分類", "支出金額"])
        category_report.to_excel(writer, sheet_name="支出分類表", index=False)
        budget_df.rename(columns={"category": "分類", "amount": "預算金額"}).to_excel(writer, sheet_name="預算設定", index=False)
        if goal is not None:
            goal_df = pd.DataFrame([{"目標名稱": goal.get("goal_name", ""), "目標金額": goal.get("target_amount", 0), "目前已存": goal.get("current_amount", 0), "完成期限": goal.get("deadline", "")}])
        else:
            goal_df = pd.DataFrame(columns=["目標名稱", "目標金額", "目前已存", "完成期限"])
        goal_df.to_excel(writer, sheet_name="儲蓄進度表", index=False)
    output.seek(0)
    return output


def main():
    st.set_page_config(page_title="AI 理財管家", page_icon="💰", layout="wide")
    init_db()
    apply_style()

    st.sidebar.title("💰 AI 理財管家")

    pages = [
        "快速記帳",
        "收支紀錄",
        "預算管理",
        "消費分析",
        "儲蓄目標",
        "AI 理財建議",
        "財務報表",
        "使用者資料",
    ]

    page = st.sidebar.selectbox(
        "功能選單",
        pages,
        key="main_page_selectbox_final_001"
    )

    selected_month = st.sidebar.text_input(
        "月份",
        value=get_month_string(),
        help="格式：YYYY-MM，例如 2026-06"
    )

    if st.sidebar.button("重新整理", use_container_width=True):
        st.rerun()

    trans_df = get_month_transactions(selected_month)
    budget_df = get_month_budgets(selected_month)
    profile = get_profile()
    goal = get_goal()

    if page == "快速記帳":
        st.markdown("# 快速記帳")
        st.caption("新增收入或支出紀錄。")
        add_transaction_box()

    elif page == "收支紀錄":
        st.markdown("# 收支紀錄")
        st.caption("查看、編輯或刪除本月收支資料。")
        transaction_records_page(trans_df)

    elif page == "預算管理":
        st.markdown("# 預算管理")
        st.caption("設定每月各分類預算，並查看使用狀況。")
        budget_page(selected_month, trans_df)

    elif page == "消費分析":
        st.markdown("# 消費分析")
        st.caption("查看分類圓餅圖、分類支出排行與每月支出趨勢。")
        analysis_charts(trans_df)

    elif page == "儲蓄目標":
        st.markdown("# 儲蓄目標")
        st.caption("設定存款目標、完成期限，並追蹤目前進度。")
        saving_goal_page()

    elif page == "AI 理財建議":
        st.markdown("# AI 理財建議")
        st.caption("根據你的收入、支出、預算與儲蓄目標，自動產生理財提醒。")

        suggestions = generate_ai_suggestions(
            selected_month,
            trans_df,
            budget_df,
            profile,
            goal
        )

        for suggestion in suggestions:
            st.markdown(
                f"<div class='quick-card'>💡 {suggestion}</div>",
                unsafe_allow_html=True
            )

    elif page == "財務報表":
        st.markdown("# 財務報表")
        st.caption("下載目前月份的 Excel 財務報表。")

        excel_file = build_excel_report(selected_month, trans_df, budget_df, goal)

        st.download_button(
            label="下載 Excel 財務報表",
            data=excel_file,
            file_name=f"AI理財管家_{selected_month}_財務報表.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    elif page == "使用者資料":
        st.markdown("# 使用者資料")
        st.caption("建立個人資料、設定每月收入與理財目標。")
        profile_page()


if __name__ == "__main__":
    main()
