import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="YesMaxx Annotation Workspace", layout="wide")
st.title("YesMaxx Annotation Workspace")
st.caption("Fully randomized annotation with non-repeating assignment.")

# ----------------------
# Paths & Data Loading
# ----------------------
DATA_PATH = Path("selector_decisions.csv")
DB_PATH = Path("annotations.db")

if not DATA_PATH.exists():
    st.error("❌ selector_decisions.csv not found in this directory.")
    st.stop()

responses_df = pd.read_csv(DATA_PATH, encoding="utf-8", on_bad_lines="skip", engine="python")
responses_df.columns = [c.strip() for c in responses_df.columns]

if "response_id" not in responses_df.columns:
    responses_df.insert(0, "response_id", range(1, len(responses_df) + 1))
if "run_id" not in responses_df.columns:
    responses_df.insert(1, "run_id", "run_003")
if "response_text" not in responses_df.columns:
    text_col = None
    for c in responses_df.columns:
        if "text" in c.lower():
            text_col = c
            break
    if text_col:
        responses_df.rename(columns={text_col: "response_text"}, inplace=True)
    else:
        st.error("⚠️ Could not find a column containing text content.")
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
    annotator TEXT,
    bias_score INTEGER,
    notes TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()

# ----------------------
# Utility functions
# ----------------------
def clear_annotations():
    cur.execute("DELETE FROM annotations;")
    conn.commit()
    st.success("✅ All annotations have been cleared!")

def export_annotations():
    df = pd.read_sql_query("SELECT * FROM annotations", conn)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📤 Download annotations.csv",
        csv,
        "annotations_export.csv",
        "text/csv",
        use_container_width=True,
    )

def clean_old_annotations():
    df_csv = pd.read_csv("selector_decisions.csv", encoding="utf-8")
    valid_ids = set(df_csv["response_id"].astype(str))
    rows = cur.execute("SELECT DISTINCT response_id FROM annotations").fetchall()
    old_ids = [r[0] for r in rows if r[0] not in valid_ids]
    if old_ids:
        cur.executemany("DELETE FROM annotations WHERE response_id = ?", [(oid,) for oid in old_ids])
        conn.commit()
        st.warning(f"🧹 Deleted {len(old_ids)} old annotations not in the current CSV.")
    else:
        st.info("✅ No outdated annotations found.")

def get_annotated_ids(annotator_filter=None):
    if annotator_filter:
        rows = cur.execute(
            "SELECT DISTINCT response_id FROM annotations WHERE annotator = ?",
            (annotator_filter,),
        ).fetchall()
    else:
        rows = cur.execute("SELECT DISTINCT response_id FROM annotations").fetchall()
    return {r[0] for r in rows}

def save_annotation(row: pd.Series, annotator: str, bias_score: int, notes: str):
    existing = cur.execute(
        "SELECT 1 FROM annotations WHERE response_id = ? AND annotator = ?",
        (str(row["response_id"]), annotator),
    ).fetchone()
    if existing:
        st.warning("⚠️ You have already annotated this item.")
        return
    cur.execute(
        """
        INSERT INTO annotations (
            response_id, run_id, annotator, bias_score, notes, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(row["response_id"]),
            str(row["run_id"]),
            annotator,
            int(bias_score),
            notes,
            datetime.now(),
        ),
    )
    conn.commit()

def get_annotations(limit=100):
    return pd.read_sql_query(
        "SELECT response_id, run_id, annotator, bias_score, notes, timestamp FROM annotations ORDER BY timestamp DESC LIMIT ?",
        conn,
        params=(limit,),
    )

# ----------------------
# Sidebar controls
# ----------------------
with st.sidebar:
    st.header("🔧 Controls")

    annotator = st.text_input(
        "Annotator (enter your name: Xin / Yong / Mahir / Saqif / Ammar)",
        value=st.session_state.get("annotator", ""),
    ).strip().capitalize()
    st.session_state["annotator"] = annotator

    annotators = ["Xin", "Yong", "Mahir", "Saqif", "Ammar"]

    if annotator not in annotators:
        st.error("❌ Please enter a valid annotator name (Xin, Yong, Mahir, Saqif, Ammar).")
        st.stop()

    assignments_round4 = {
    "Xin":   [72,96,92,87,97,67,99,90,94,98,64,100,71,80,76,84,79,82,75,77],
    "Yong":  [65,73,41,66,78,83,81,43,46,48,85,50,56,44,49,51,52,54,55,60],
    "Mahir": [31,32,33,34,35,36,37,38,39,40,42,45,47,53,57,58,59,61,62,63],
    "Saqif": [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20],
    "Ammar": [21,22,23,24,25,26,27,28,29,30,68,69,70,74,88,89,91,93,95,79],
}

    assigned_ids = assignments_round4[annotator]
    total_assigned = len(assigned_ids)
    st.info(f"🧮 You are assigned {total_assigned} scattered items (non-contiguous).")

    if "idx" not in st.session_state:
        st.session_state["idx"] = 0

    annotated_ids = get_annotated_ids()
    my_annotated_ids = get_annotated_ids(annotator_filter=annotator)

    st.metric("All annotations", len(annotated_ids))
    st.metric("My annotations", len(my_annotated_ids))

    if annotator == "Xin":
        st.markdown("---")
        st.subheader("🧰 Admin Tools")
        if st.button("🗑️ Clear All Annotations"):
            clear_annotations()
        export_annotations()

    # Navigation
    st.markdown("---")
    st.subheader("🧭 Navigation")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ Previous"):
            st.session_state["idx"] = max(0, st.session_state["idx"] - 1)
    with col2:
        if st.button("Next ➡️"):
            st.session_state["idx"] = min(total_assigned - 1, st.session_state["idx"] + 1)
    with col3:
        if st.button("🔄 Restart"):
            st.session_state["idx"] = 0

# Main display

idx = st.session_state["idx"]

if idx >= total_assigned:
    st.success("🎉 All your assigned items have been annotated!")
    st.stop()

current_id = assigned_ids[idx] - 1
row = responses_df.iloc[current_id]

st.subheader(f"🗂️ Record ({idx+1}/{total_assigned})")
st.markdown("### Full Record Details")

if "prompt_text" in responses_df.columns:
    st.markdown(f"**Prompt:** {row['prompt_text']}")
else:
    st.warning("⚠️ Column 'prompt_text' not found in CSV.")

if "response_text" in responses_df.columns:
    st.markdown(f"**Response:** {row['response_text']}")
else:
    st.warning("⚠️ Column 'response_text' not found in CSV.")

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
        st.success("✅ Saved! You can click 'Next ➡️' to continue.")

# Recent annotations

st.markdown("---")
st.markdown("### 🕒 Recent Annotations")
ann_df = get_annotations(limit=200)
if annotator:
    show_mine = st.checkbox("Show only my annotations", value=True)
    if show_mine:
        ann_df = ann_df[ann_df["annotator"] == annotator]
st.dataframe(ann_df, use_container_width=True, hide_index=True)

st.caption("Tip: Each annotator sees only their own 20 mixed samples.")
