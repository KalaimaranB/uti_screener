import streamlit as st
from datetime import datetime
from pathlib import Path
import tempfile
import pandas as pd
import streamlit.components.v1 as components

#Image analysis file
# from image_analysis_runner import analyze_uploaded_image

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

                # Image analysis temporarily disabled while troubleshooting page loading.
                # #Image analysis skeleton:
                # with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as temp_file:
                #     temp_file.write(uploaded_file.getbuffer())
                #     temp_file_path = temp_file.name

                # analysis_result = analyze_uploaded_image(temp_file_path)
                # st.session_state.analysis_output = analysis_result

                # upload_status = analysis_result.get("status", "Analysis complete")
                upload_status = "Analysis step temporarily disabled"

        screening_result = upload_status

        history_row = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Name": patient_name or "Not provided",
            "Sample Date": sample_date.strftime("%Y-%m-%d") if sample_date else "Not provided",
            "Collection Time": str(collection_time),
            "Age": patient_age,
            "Sex": sex,
            "Filename": uploaded_filename,
            "Result": screening_result,
            "Analysis Summary": (
                st.session_state.analysis_output.get("summary", "Not available")
                if st.session_state.analysis_output
                else "Not available"
            ),
            "Notes": notes or "None",
        }
        st.session_state.upload_history.append(history_row)

screening_result = "Not generated yet"
if st.session_state.upload_history:
    screening_result = st.session_state.upload_history[-1]["Result"]

if st.session_state.analysis_started:
    st.divider()
    st.subheader("Generated Report")

    st.write(f"**Name:** {patient_name or 'Not provided'}")
    st.write(f"**Sample Date:** {sample_date.strftime('%Y-%m-%d') if sample_date else 'Not provided'}")
    st.write(f"**Age:** {patient_age}")
    st.write(f"**Sex:** {sex}")
    st.write(f"**Collection Time:** {collection_time}")
    st.write(f"**Clinical Notes:** {notes or 'None'}")

    st.write("### Preliminary interpretation")
    st.write(
        f"The uploaded file status is **{screening_result}**. "
        "This is only a screening-style interface and not a medical diagnosis."
    )

    if st.session_state.analysis_output:
        st.write("### Image analysis output")
        st.write(f"**Analysis status:** {st.session_state.analysis_output.get('status', 'Not available')}")
        st.write(f"**Summary:** {st.session_state.analysis_output.get('summary', 'Not available')}")
        st.write(f"**Detected class:** {st.session_state.analysis_output.get('detected_class', 'Not available')}")
        st.write(f"**Confidence:** {st.session_state.analysis_output.get('confidence', 'Not available')}")


    history_df = pd.DataFrame(st.session_state.upload_history)

    st.write("### Upload history")
    st.table(history_df)

    csv_data = history_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download upload history as CSV",
        data=csv_data,
        file_name="uti_upload_history.csv",
        mime="text/csv",
    )

    st.write("### Print-friendly report")
    printable_html = history_df.to_html(index=False)
    components.html(
        f"""
        <div style='font-family: Arial, sans-serif; padding: 8px;'>
            <h3>UTI Upload History Report</h3>
            <p>This report is formatted for printing and sharing with a doctor.</p>
            {printable_html}
            <button onclick='window.print()' style='margin-top: 12px; padding: 8px 12px; cursor: pointer;'>Print Report</button>
        </div>
        """,
        height=600,
        scrolling=True,
    )