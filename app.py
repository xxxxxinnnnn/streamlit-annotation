import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="YesMaxx Annotation Workspace", layout="wide")
st.title("📝 YesMaxx Annotation Workspace")
st.caption("Annotation UI for full selector_decisions.csv dataset")

# ----------------------
# Paths & Data Loading
# ----------------------
DATA_PATH = Path("selector_decisions.csv")  # 👈 自动读取完整文件
DB_PATH = Path("annotations.db")

# Load data
if not DATA_PATH.exists():
    st.error("❌ selector_decisions.csv not found. Please upload it to the same folder.")
    st.stop()

# Read robustly
responses_df = pd.read_csv(DATA_PATH, encoding="utf-8", on_bad_lines="skip", engine="python")
responses_df.columns = [c.strip() for c in responses_df.columns]

# Validate basic structure
if "response_id" not in responses_df.columns:
    responses_df.insert(0, "response_id", range(1, len(responses_df) + 1))
if "run_id" not in responses_df.columns:
    responses_df.insert(1, "run_id", "run_001")
if "response_text" not in responses_df.columns:
    # try to auto-detect text-like column
    text_col = None
    for c in responses_df.columns:
        if "text" in c.lower():
            text_col = c
            break
    if text_col:
        responses_df.rename(columns={text_col: "response_text"}, inplace=True)
    else:
        st.error("⚠️ Could not find any column with text content.")
        st.stop()

# ----------------------
# Database Setup
# ----------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS annotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id TEXT,
        run_id TEXT,
        response_text TEXT,
        annotator TEXT,
        bias_score INTEGER,
        notes TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
""")
conn.commit()

# ----------------------
# Helper functions
# ----------------------
def get_annotated_ids(annotator_filter=None):
    if annotator_filter:
        rows = cur.execute("SELECT DISTINCT response_id FROM annotations WHERE annotator = ?", (annotator_filter,)).fetchall()
    else:
        rows = cur.execute("SELECT DISTINCT response_id FROM annotations").fetchall()
    return {r[0] for r in rows}

def save_annotation(row: pd.Series, annotator: str, bias_score: int, notes: str):
    cur.execute("""
        INSERT INTO annotations (
            response_id, run_id, response_text, annotator, bias_score, notes, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        str(row["response_id"]), str(row["run_id"]), str(row["response_text"]),
        annotator, int(bias_score), notes, datetime.now()
    ))
    conn.commit()

def get_annotations(limit=100):
    return pd.read_sql_query(
        "SELECT response_id, run_id, annotator, bias_score, notes, timestamp FROM annotations ORDER BY timestamp DESC LIMIT ?",
        conn, params=(limit,)
    )

# ----------------------
# Sidebar
# ----------------------
with st.sidebar:
    st.header("🔧 Controls")
    annotator = st.text_input("Annotator (your name or ID)", value=st.session_state.get("annotator", ""))
    st.session_state["annotator"] = annotator

    if "idx" not in st.session_state:
        st.session_state["idx"] = 0

    total = len(responses_df)
    annotated_ids = get_annotated_ids()
    my_annotated_ids = get_annotated_ids(annotator_filter=annotator) if annotator else set()

    st.metric("Total samples", total)
    st.metric("All annotations", len(annotated_ids))
    st.metric("My annotations", len(my_annotated_ids))

    def jump_to_next_unannotated():
        current = st.session_state["idx"]
        annotated = get_annotated_ids(annotator_filter=annotator) if annotator else get_annotated_ids()
        for offset in range(total):
            i = (current + offset) % total
            item_id = str(responses_df.iloc[i]["response_id"])
            if item_id not in annotated:
                st.session_state["idx"] = i
                return
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ Previous"):
            st.session_state["idx"] = (st.session_state["idx"] - 1) % total
    with col2:
        if st.button("Next ➡️"):
            st.session_state["idx"] = (st.session_state["idx"] + 1) % total
    with col3:
        if st.button("Jump to Unannotated"):
            jump_to_next_unannotated()

# ----------------------
# Main Display
# ----------------------
idx = st.session_state["idx"]
row = responses_df.iloc[idx]

st.subheader(f"🗂️ Record {idx+1}/{total}")
st.markdown("### Full Record Details")

# ✅ 显示所有列的内容（每列单独一行）
for col in responses_df.columns:
    st.markdown(f"**{col}:** {row[col]}")

st.markdown("---")
st.markdown("### Annotate Now")
with st.form("annotation_form", clear_on_submit=True):
    bias_score = st.slider("Bias Score (1 = No bias, 5 = Strong bias)", 1, 5, 3)
    notes = st.text_area("Notes (optional)", "")
    submitted = st.form_submit_button("Submit ✅", use_container_width=True)

if submitted:
    if not annotator:
        st.error("⚠️ Please enter your name/ID in the sidebar before annotating.")
    else:
        save_annotation(row, annotator, bias_score, notes)
        st.success("✅ Annotation saved! Click 'Next' to continue.")

# ----------------------
# Recent Annotations
# ----------------------
st.markdown("---")
st.markdown("### Recent Annotations")
ann_df = get_annotations(limit=200)
if annotator:
    show_mine = st.checkbox("Show only my annotations", value=False)
    if show_mine:
        ann_df = ann_df[ann_df["annotator"] == annotator]
st.dataframe(ann_df, use_container_width=True, hide_index=True)

st.caption("Tip: This app automatically displays all columns from selector_decisions.csv.")
