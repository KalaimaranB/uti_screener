import streamlit as st
from datetime import datetime
from pathlib import Path
import tempfile
import pandas as pd
import streamlit.components.v1 as components

#Image analysis module
import os
import json
from api.image_analysis_runner import analyze_uploaded_image

@st.cache_data
def load_diagnostics_model():
    with open("models/model.json", "r") as f:
        return json.load(f)

model_spec = load_diagnostics_model()

#Page set up info:
st.set_page_config(
    page_title="UTI Screening",
    layout="wide",
)

#Set session state:
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

                with st.status("Initializing Analysis Pipeline...", expanded=True) as status_box:
                    def update_status(msg):
                        status_box.update(label=msg)
                    
                    analysis_result = analyze_uploaded_image(temp_file_path, progress_callback=update_status)
                    st.session_state.analysis_output = analysis_result
                    upload_status = analysis_result.get("status", "Analysis complete")
                    
                    status_box.update(label="Sequence Completed Successfully!", state="complete", expanded=False)

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
    # Use "Status" key to correctly fetch the history item since we renamed it from "Result"
    screening_result = st.session_state.upload_history[-1].get("Status", "Not generated yet")

if st.session_state.analysis_started:
    st.divider()
    st.divider()
    st.subheader("Generated Patient Report")

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
        st.write("---")
        st.subheader("Diagnostic Feedback")
        
        conf_col, class_col = st.columns(2)
        conf_col.metric("Aggregate Confidence", st.session_state.analysis_output.get('confidence', 'N/A'))
        class_col.metric("Recognized Target", st.session_state.analysis_output.get('detected_class', 'N/A').title())
        
        with st.expander("🔬 View Detailed Clinical Interpretation", expanded=False):
            summary_text = st.session_state.analysis_output.get('summary', 'Not available')
            for line in summary_text.split('\\n'):
                if line.strip():
                    st.write(f"- {line.strip()}")
        
        biomarkers = st.session_state.analysis_output.get("biomarkers", {})
        if biomarkers:
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
                col_name, col_color, col_val, col_conf, col_graph = st.columns([1.5, 1, 2, 2, 3])
                
                with col_name:
                    st.write(f"{key.capitalize()}")
                
                with col_color:
                    r, g, b = data.get("color_rgb", (200, 200, 200))
                    # Draw actual sampled color
                    st.markdown(
                        f"""<div style="width:24px; height:24px; background-color: rgb({r},{g},{b}); border: 1px solid #ddd; border-radius: 4px;"></div>""",
                        unsafe_allow_html=True
                    )
                
                with col_val:
                    st.write(f"{data.get('value')} {data.get('unit')}")
                    
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
                                    # HTML Gauge styling with relative parameter scales
                                    st.markdown(
                                        f"""
                                        <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.8em; color: gray; margin-bottom: 2px;">
                                            <span>{v_min} {data.get('unit')}</span>
                                            <span>{v_max} {data.get('unit')}</span>
                                        </div>
                                        <div style="width: 100%; background-color: #e0e0e0; border-radius: 4px; height: 8px;">
                                            <div style="width: {prog*100}%; background-color: #4CAF50; height: 100%; border-radius: 4px;"></div>
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
        
        debug_img_path = st.session_state.analysis_output.get('debug_image_path')
        if debug_img_path and os.path.exists(debug_img_path):
            with st.expander("🖼️ View Raw Annotated Debug Scan", expanded=False):
                st.image(debug_img_path, caption="Computer Vision Detection Boundaries", use_container_width=True)
            with open(debug_img_path, "rb") as file:
                st.download_button(
                        label="⬇️ Download Annotated Debug Scan",
                        data=file,
                        file_name="uti_debug_annotated.png",
                        mime="image/png"
                    )

    st.write("---")
    st.subheader("Session History")
    history_df = pd.DataFrame(st.session_state.upload_history)
    
    st.dataframe(history_df, use_container_width=True, hide_index=True)

    csv_data = history_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download simplified history CSV",
        data=csv_data,
        file_name="uti_screening_history.csv",
        mime="text/csv",
    )