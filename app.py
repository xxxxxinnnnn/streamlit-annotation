import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="YesMaxx Annotation Workspace", layout="wide")
st.title("📝 YesMaxx Annotation Workspace")
st.caption("Annotation UI for response_text dataset")

# ----------------------
# Paths & Data Loading
# ----------------------
DATA_PATH = Path("responses.csv")
DB_PATH = Path("annotations.db")

# Load responses
if not DATA_PATH.exists():
    st.warning("responses.csv not found. Creating a sample file.")
    sample = pd.DataFrame([
        {"response_id": "rsp_sample_001", "run_id": "run_sample", "response_text": "This is a sample response text."}
    ])
    sample.to_csv(DATA_PATH, index=False)

# Try reading CSV robustly
try:
    responses_df = pd.read_csv(DATA_PATH, encoding="utf-8", sep=",", on_bad_lines="skip", engine="python")
except Exception:
    # fallback for space-separated files
    responses_df = pd.read_csv(DATA_PATH, encoding="utf-8", delim_whitespace=True, on_bad_lines="skip", engine="python")

# fix column names
responses_df.columns = [c.strip() for c in responses_df.columns]

# auto-rename and merge if needed
if set(responses_df.columns) != {"response_id", "run_id", "response_text"}:
    # if the file has 3+ columns, merge extras into response_text
    if len(responses_df.columns) >= 3:
        responses_df.rename(columns={responses_df.columns[0]: "response_id",
                                     responses_df.columns[1]: "run_id",
                                     responses_df.columns[2]: "response_text"}, inplace=True)
        # merge any extra columns into response_text
        if len(responses_df.columns) > 3:
            responses_df["response_text"] = responses_df.apply(
                lambda x: " ".join([str(v) for v in x[2:].tolist() if pd.notnull(v)]),
                axis=1
            )
            responses_df = responses_df[["response_id", "run_id", "response_text"]]
    else:
        st.error("Your CSV must contain at least 3 columns: response_id, run_id, response_text.")
        st.stop()

required_cols = {"response_id", "run_id", "response_text"}
missing = required_cols - set(responses_df.columns)
if missing:
    st.error(f"responses.csv is missing required columns: {missing}")
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

def get_annotations(limit=50):
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
st.subheader(f"Response {idx+1}/{total}")
st.markdown(f"**Response ID:** {row['response_id']}")
st.markdown(f"**Run ID:** {row['run_id']}")

st.markdown("#### Response Text")
st.write(str(row["response_text"]))

st.markdown("---")
st.markdown("### Annotate Now")
with st.form("annotation_form", clear_on_submit=True):
    bias_score = st.slider("Bias Score (1=No bias, 5=Strong bias)", 1, 5, 3)
    notes = st.text_area("Notes (optional)", "")
    submitted = st.form_submit_button("Submit ✅", use_container_width=True)
if submitted:
    if not annotator:
        st.error("Please enter your name/ID in the sidebar before annotating.")
    else:
        save_annotation(row, annotator, bias_score, notes)
        st.success("Saved! You can click 'Next' to continue.")

# ----------------------
# Recent Annotations
# ----------------------
st.markdown("---")
st.markdown("### Recent Annotations")
ann_df = get_annotations(limit=100)
if annotator:
    show_mine = st.checkbox("Show only my annotations", value=False)
    if show_mine:
        ann_df = ann_df[ann_df["annotator"] == annotator]
st.dataframe(ann_df, use_container_width=True, hide_index=True)

st.caption("Tip: CSV columns can be space- or comma-separated; app auto-fixes column alignment.")
