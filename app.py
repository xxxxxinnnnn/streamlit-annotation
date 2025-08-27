import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="YesMaxx Annotation Workspace", layout="wide")
st.title("📝 YesMaxx Annotation Workspace")
st.caption("Minimal UI + SQLite schema + read/write smoke test")

# ----------------------
# Paths & Data Loading
# ----------------------
DATA_PATH = Path("prompts.csv")
DB_PATH = Path("annotations.db")

# Load prompts
if not DATA_PATH.exists():
    st.warning("prompts.csv not found. Creating a sample file.")
    sample = pd.DataFrame([{
        "id": 1, "prompt": "Sample prompt", "model_output": "Sample answer", "model_name": "ModelA",
        "topic": "sample", "region": "Global", "stance": "neutral", "intensity": "low"
    }])
    sample.to_csv(DATA_PATH, index=False)

prompts_df = pd.read_csv(DATA_PATH)
required_cols = {"id","prompt","model_output","model_name","topic","region","stance","intensity"}
missing = required_cols - set(prompts_df.columns)
if missing:
    st.error(f"prompts.csv is missing required columns: {missing}")
    st.stop()

# ----------------------
# Database Setup
# ----------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS annotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        prompt TEXT,
        model_output TEXT,
        model_name TEXT,
        topic TEXT,
        region TEXT,
        stance TEXT,
        intensity TEXT,
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
def get_annotated_item_ids(annotator_filter=None):
    if annotator_filter:
        rows = cur.execute("SELECT DISTINCT item_id FROM annotations WHERE annotator = ?", (annotator_filter,)).fetchall()
    else:
        rows = cur.execute("SELECT DISTINCT item_id FROM annotations").fetchall()
    return {r[0] for r in rows}

def save_annotation(row: pd.Series, annotator: str, bias_score: int, notes: str):
    cur.execute("""
        INSERT INTO annotations (
            item_id, prompt, model_output, model_name, topic, region, stance, intensity,
            annotator, bias_score, notes, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(row["id"]), str(row["prompt"]), str(row["model_output"]), str(row["model_name"]),
        str(row["topic"]), str(row["region"]), str(row["stance"]), str(row["intensity"]),
        annotator, int(bias_score), notes, datetime.now()
    ))
    conn.commit()

def get_annotations(limit=50):
    return pd.read_sql_query(
        "SELECT item_id, annotator, bias_score, notes, model_name, topic, region, stance, intensity, timestamp FROM annotations ORDER BY timestamp DESC LIMIT ?",
        conn, params=(limit,)
    )

# ----------------------
# Sidebar (Annotator / Filters / Navigation)
# ----------------------
with st.sidebar:
    st.header("🔧 Controls")
    annotator = st.text_input("Annotator (your name or ID)", value=st.session_state.get("annotator",""))
    st.session_state["annotator"] = annotator

    # Index state
    if "idx" not in st.session_state:
        st.session_state["idx"] = 0

    total = len(prompts_df)
    annotated_ids = get_annotated_item_ids(annotator_filter=None)
    my_annotated_ids = get_annotated_item_ids(annotator_filter=annotator) if annotator else set()
    st.metric("Total samples", total)
    st.metric("All annotations", len(annotated_ids))
    st.metric("My annotations", len(my_annotated_ids))

    def jump_to_next_unannotated():
        current = st.session_state["idx"]
        annotated = get_annotated_item_ids(annotator_filter=annotator) if annotator else get_annotated_item_ids()
        for offset in range(total):
            i = (current + offset) % total
            item_id = int(prompts_df.iloc[i]["id"])
            if item_id not in annotated:
                st.session_state["idx"] = i
                return
        return

    col_nav1, col_nav2, col_nav3 = st.columns(3)
    with col_nav1:
        if st.button("⬅️ Previous"):
            st.session_state["idx"] = (st.session_state["idx"] - 1) % total
    with col_nav2:
        if st.button("Next ➡️"):
            st.session_state["idx"] = (st.session_state["idx"] + 1) % total
    with col_nav3:
        if st.button("Jump to Unannotated"):
            jump_to_next_unannotated()

    st.divider()
    st.subheader("🧪 Smoke Test")
    if st.button("Run Write/Read Test"):
        dummy = prompts_df.iloc[0]
        save_annotation(dummy, annotator or "tester", 3, "smoke test")
        st.success("✅ A test record has been inserted. Check it below.")

# ----------------------
# Main Item View
# ----------------------
idx = st.session_state["idx"]
row = prompts_df.iloc[idx]
st.subheader(f"Sample {idx+1} / {total}  •  ID={int(row['id'])}  •  Model={row['model_name']}")
meta_cols = st.columns(4)
meta_cols[0].markdown(f"**Topic:** {row['topic']}")
meta_cols[1].markdown(f"**Region:** {row['region']}")
meta_cols[2].markdown(f"**Stance:** {row['stance']}")
meta_cols[3].markdown(f"**Intensity:** {row['intensity']}")

st.markdown("#### Prompt")
st.info(str(row["prompt"]))
st.markdown("#### Model Output")
st.write(str(row["model_output"]))

# Annotation form
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
# Recent Annotations Table
# ----------------------
st.markdown("---")
st.markdown("### Recent Annotations")
ann_df = get_annotations(limit=100)
if annotator:
    show_mine = st.checkbox("Show only my annotations", value=False)
    if show_mine:
        ann_df = ann_df[ann_df["annotator"] == annotator]
st.dataframe(ann_df, use_container_width=True, hide_index=True)

st.caption("Tip: Replace prompts.csv with your own data. Each row should have (Prompt, Model Output, Model). Refresh the page to load.")
