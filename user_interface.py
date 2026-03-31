import streamlit as st
from datetime import datetime
from pathlib import Path
import tempfile
import pandas as pd
import streamlit.components.v1 as components

# Image analysis module
import os
import json
from api.image_analysis_runner import analyze_uploaded_image

@st.cache_data
def load_diagnostics_model():
    with open("models/model.json", "r") as f:
        return json.load(f)

model_spec = load_diagnostics_model()

# Page set up info:
st.set_page_config(
    page_title="UTI Screening",
    layout="wide",
)

st.markdown("""
    <style>
    #custom-loader {
        position: fixed;
        top: 0; left: 0;
        width: 100vw; height: 100vh;
        background: #0e1117;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        animation: fadeOut 0.5s ease 2s forwards;
    }
    #custom-loader h2 {
        color: white;
        font-family: sans-serif;
        margin-top: 16px;
        letter-spacing: 0.05em;
    }
    #custom-loader p {
        color: #888;
        font-family: sans-serif;
        font-size: 0.85em;
        margin-top: 6px;
    }
    .loader-bar {
        width: 220px;
        height: 4px;
        background: #1e1e1e;
        border-radius: 4px;
        overflow: hidden;
        margin-top: 16px;
    }
    .loader-bar-fill {
        height: 100%;
        width: 0%;
        background: #ff4b4b;
        border-radius: 4px;
        animation: fillBar 1.8s ease forwards;
    }
    @keyframes fillBar {
        to { width: 100%; }
    }
    @keyframes fadeOut {
        to { opacity: 0; pointer-events: none; }
    }
    </style>

    <div id="custom-loader">
        <h2>UTI Analyzer</h2>
        <p>Initializing screening interface...</p>
        <div class="loader-bar">
            <div class="loader-bar-fill"></div>
        </div>
    </div>
""", unsafe_allow_html=True)

# Set session state:
if "analysis_started" not in st.session_state:
    st.session_state.analysis_started = False
if "upload_history" not in st.session_state:
    st.session_state.upload_history = []

if "analysis_output" not in st.session_state:
    st.session_state.analysis_output = None

st.title("UTI Analyzer")
st.markdown(
    """
    <style>
    /* Make hovered and selected days use the same fixed-size circular day chip */
    div[data-baseweb="calendar"] [role="gridcell"] > div,
    div[data-baseweb="calendar"] [role="gridcell"] button,
    div[data-baseweb="calendar"] [role="gridcell"] span {
        width: 36px !important;
        height: 36px !important;
        min-width: 36px !important;
        min-height: 36px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        border-radius: 50% !important;
        transition: background-color 0.2s ease, color 0.2s ease;
        box-sizing: border-box !important;
    }

    div[data-baseweb="calendar"] [role="gridcell"] {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    div[data-baseweb="calendar"] [role="gridcell"]:hover > div,
    div[data-baseweb="calendar"] [role="gridcell"]:hover button,
    div[data-baseweb="calendar"] [role="gridcell"]:hover span {
        background: rgba(255, 0, 0, 0.14) !important;
        color: white !important;
        border-radius: 50% !important;
        box-shadow: none !important;
    }

    div[data-baseweb="calendar"] [role="gridcell"]:hover *,
    div[data-baseweb="calendar"] [role="gridcell"]:hover button *,
    div[data-baseweb="calendar"] [role="gridcell"]:hover span * {
        color: white !important;
    }

    div[data-baseweb="calendar"] [aria-selected="true"],
    div[data-baseweb="calendar"] [aria-selected="true"] > div,
    div[data-baseweb="calendar"] [aria-selected="true"] button,
    div[data-baseweb="calendar"] [aria-selected="true"] span {
        width: 36px !important;
        height: 36px !important;
        min-width: 36px !important;
        min-height: 36px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        background: rgba(255, 0, 0, 0.25) !important;
        color: white !important;
        border-radius: 50% !important;
        box-shadow: none !important;
        box-sizing: border-box !important;
    }

    div[data-baseweb="calendar"] [aria-selected="true"] *,
    div[data-baseweb="calendar"] [aria-selected="true"] button *,
    div[data-baseweb="calendar"] [aria-selected="true"] span * {
        color: white !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.caption("Designed for home use: upload your test file, review your information, and generate a simple at-home UTI screening summary.")

with st.sidebar:
    st.header("Patient Info")
    patient_name = st.text_input("Name *", placeholder="Enter your name e.g. First, Last")
    sample_date = st.date_input("Sample Date *")
    collection_time = st.time_input("Collection Time *")
    patient_age = st.number_input("Age", min_value=0, max_value=120, value=25)
    sex = st.selectbox("Sex", ["Female", "Male", "Other", "Prefer not to say"])
    notes = st.text_area("Notes", placeholder="Enter any additional information here...")

left_col, right_col = st.columns([1.2, 1])

with left_col:
    st.subheader("Upload Your Test Image")
    uploaded_file = st.file_uploader(
        "Upload your test strip image from your phone",
        type=["png", "jpg", "jpeg", "csv"],
        help="Choose a photo or file from your device."
    )

    st.caption("This section is intended for at-home users uploading their own test results.")

    start_button = st.button("Generate Results")

with right_col:
    st.subheader("Live Summary")
    st.info(
        "This page is designed for a patient using the tool at home. Upload your file, review your entries, and generate a summary."
    )

    if uploaded_file is not None:
        st.success(f"Uploaded file: {uploaded_file.name}")
    else:
        st.warning("File not uploaded")

if start_button:
    st.session_state.analysis_started = True

    missing_required_fields = []
    if not patient_name.strip():
        missing_required_fields.append("Name")
    if not sample_date:
        missing_required_fields.append("Sample Date")

    if missing_required_fields:
        st.session_state.analysis_started = False
        st.error("Please fill in all required fields: " + ", ".join(missing_required_fields))

    if st.session_state.analysis_started:
        allowed_suffixes = {".png", ".jpg", ".jpeg"}
        max_file_size_mb = 10
        max_file_size_bytes = max_file_size_mb * 1024 * 1024

        upload_status = "Ready for analysis"
        uploaded_filename = "Not provided"

        if uploaded_file is None:
            upload_status = "File not uploaded"
        else:
            uploaded_filename = uploaded_file.name
            file_suffix = Path(uploaded_file.name).suffix.lower()
            file_size_bytes = uploaded_file.size

            if file_suffix not in allowed_suffixes:
                upload_status = "Invalid file type"
            elif file_size_bytes > max_file_size_bytes:
                upload_status = f"File too large (max {max_file_size_mb} MB)"
            else:
                upload_status = "Running analysis"

                with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as temp_file:
                    temp_file.write(uploaded_file.getbuffer())
                    temp_file_path = temp_file.name

                progress_bar = st.progress(0, text="Initializing Analysis Pipeline...")
                status_text = st.empty()

                step_messages = []

                def update_status(msg):
                    step_messages.append(msg)
                    # Estimate progress based on how many updates have come in (cap at 95%)
                    estimated_progress = min(0.95, len(step_messages) * 0.2)
                    progress_bar.progress(estimated_progress, text=msg)
                    status_text.caption(f"Step {len(step_messages)}: {msg}")

                analysis_result = analyze_uploaded_image(temp_file_path, progress_callback=update_status)
                st.session_state.analysis_output = analysis_result
                upload_status = analysis_result.get("status", "Analysis complete")

                progress_bar.progress(1.0, text="Sequence Completed Successfully!")
                status_text.empty()

                # Clean up the initial temp file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

        screening_result = upload_status

        history_row = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Name": patient_name or "Not provided",
            "Age/Sex": f"{patient_age} {sex[0] if sex else ''}",
            "Filename": Path(uploaded_filename).name,
            "Status": screening_result
        }
        st.session_state.upload_history.append(history_row)

screening_result = "Not generated yet"
if st.session_state.upload_history:
    screening_result = st.session_state.upload_history[-1].get("Status", "Not generated yet")

if st.session_state.analysis_started:
    st.divider()
    st.subheader("Generated Patient Report")
    
    # Introduce Tabs to organize the layout
    tab_report, tab_diagnostics, tab_history = st.tabs([
        "📝 Current Report", 
        "🔬 Diagnostics & Images", 
        "🕒 History"
    ])

    # --- TAB 1: CURRENT REPORT ---
    with tab_report:
        col1, col2, col3 = st.columns(3)
        col1.metric("Patient", patient_name or 'Not provided')
        col2.metric("Age & Sex", f"{patient_age} / {sex}")
        col3.metric("Sample Date", sample_date.strftime('%Y-%m-%d') if sample_date else 'Not provided')

        st.caption(f"**Collection Time:** {collection_time} | **Notes:** {notes or 'None'}")

        st.info(
            f"**Pipeline Status**: {screening_result} \n\n"
            "*Disclaimer: This is a preliminary screening interface and is not a substitute for a clinical medical diagnosis.*"
        )

        if st.session_state.analysis_output:
            biomarkers = st.session_state.analysis_output.get("biomarkers", {})
            if biomarkers:
                st.write("---")
                st.markdown("##### Parameter Readouts")
                
                # Create cleanly aligned columns for the table header
                h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([1.5, 1, 2, 2, 3])
                h_col1.markdown("**Analyte**")
                h_col2.markdown("**Swatch**")
                h_col3.markdown("**Quantity**")
                h_col4.markdown("**Confidence**")
                h_col5.markdown("**Normal Bounds**")
                st.divider()

                for key, data in biomarkers.items():
                    # Wrap each row in a container to visually group the data
                    with st.container(border=True):
                        
                        col_name, col_color, col_val, col_conf, col_graph = st.columns([1.5, 1, 2, 2, 3])
                        
                        with col_name:
                            st.write(f"**{key.capitalize()}**") 
                        
                        with col_color:
                            r, g, b = data.get("color_rgb", (200, 200, 200))
                            st.markdown(
                                f"""<div style="width:24px; height:24px; background-color: rgb({r},{g},{b}); border: 1px solid #ddd; border-radius: 4px;"></div>""",
                                unsafe_allow_html=True
                            )
                        
                        with col_val:
                            val = data.get('value')
                            unit = data.get('unit', '')
                            if str(val).upper() == "NEGATIVE":
                                st.write("NEGATIVE")
                            else:
                                st.write(f"{val} {unit}")
                                
                        with col_conf:
                            conf_val = data.get('confidence', 0)
                            if isinstance(conf_val, float):
                                st.write(f"{conf_val:.1%}")
                            else:
                                st.write(str(conf_val))
                        
                        with col_graph:
                            # Dynamically get numerical extremes from configuration
                            b_cfg = model_spec.get(key, {})
                            if b_cfg.get("type", "") == "numeric":
                                swatch_vals = [s.get("value") for s in b_cfg.get("swatches", [])]
                                if swatch_vals:
                                    v_min = min(swatch_vals)
                                    v_max = max(swatch_vals)
                                    current_val = data.get("value")
                                    try:
                                        current_val = float(current_val)
                                        if v_max > v_min:
                                            prog = (current_val - v_min) / (v_max - v_min)
                                            prog = max(0.0, min(1.0, prog))
                                            
                                            # DYNAMIC COLOR ALERT LOGIC
                                            if prog < 0.1 or prog > 0.9:
                                                bar_color = "#FF4B4B" # Red for extreme abnormal
                                            elif prog < 0.25 or prog > 0.75:
                                                bar_color = "#FFA421" # Orange/Yellow for borderline
                                            else:
                                                bar_color = "#4CAF50" # Green for normal

                                            # HTML Gauge styling with dynamic relative parameter scales
                                            st.markdown(
                                                f"""
                                                <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.8em; color: gray; margin-bottom: 2px;">
                                                    <span>{v_min} {data.get('unit')}</span>
                                                    <span>{v_max} {data.get('unit')}</span>
                                                </div>
                                                <div style="width: 100%; background-color: #e0e0e0; border-radius: 4px; height: 8px;">
                                                    <div style="width: {prog*100}%; background-color: {bar_color}; height: 100%; border-radius: 4px;"></div>
                                                </div>
                                                """, 
                                                unsafe_allow_html=True
                                            )
                                        else:
                                            st.caption("Categorical Boundary")
                                    except (ValueError, TypeError):
                                        st.caption("Categorical Target")
                                else:
                                    st.caption("--")
                            else:
                                st.caption("Qualitative")

    # --- TAB 2: DIAGNOSTICS & IMAGES ---
    with tab_diagnostics:
        if st.session_state.analysis_output:
            conf_col, class_col = st.columns(2)
            conf_col.metric("Aggregate Confidence", st.session_state.analysis_output.get('confidence', 'N/A'))
            class_col.metric("Recognized Target", st.session_state.analysis_output.get('detected_class', 'N/A').title())
            
            with st.expander("🔬 View Detailed Clinical Interpretation", expanded=True):
                summary_text = st.session_state.analysis_output.get('summary', 'Not available')
                for line in summary_text.split('\\n'):
                    if line.strip():
                        st.write(f"- {line.strip()}")
            
            debug_img_path = st.session_state.analysis_output.get('debug_image_path')
            if debug_img_path and os.path.exists(debug_img_path):
                with st.expander("🖼️ View Raw Annotated Debug Scan", expanded=True):
                    st.image(debug_img_path, caption="Computer Vision Detection Boundaries", use_container_width=True)
                with open(debug_img_path, "rb") as file:
                    st.download_button(
                            label="⬇️ Download Annotated Debug Scan",
                            data=file,
                            file_name="uti_debug_annotated.png",
                            mime="image/png"
                        )
        else:
            st.info("Run an analysis to view diagnostic feedback and imaging.")

    # --- TAB 3: HISTORY ---
    with tab_history:
        history_df = pd.DataFrame(st.session_state.upload_history)
        
        # Convert Timestamp to actual datetime object so Column Config can format it
        if not history_df.empty:
            history_df["Timestamp"] = pd.to_datetime(history_df["Timestamp"])
        
        st.dataframe(
            history_df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Timestamp": st.column_config.DatetimeColumn("Date & Time", format="MMM D, YYYY, h:mm a"),
                "Status": st.column_config.TextColumn("Pipeline Status", width="medium"),
            }
        )

        csv_data = history_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download simplified history CSV",
            data=csv_data,
            file_name="uti_screening_history.csv",
            mime="text/csv",
        )