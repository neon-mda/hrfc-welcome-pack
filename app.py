from pathlib import Path
import io
import zipfile
import pandas as pd
import streamlit as st
from PIL import Image

# Import the core engine functions
from render_pitch_map import (
    BASE_DIR,
    OUTPUT_DIR,
    generate_pitch_map,
    load_opponent_crest,
)

CONFIG_PATH = BASE_DIR / "config.xlsx"

st.set_page_config(
    page_title="HRFC Pitch Map Generator",
    page_icon="🏉",
    layout="wide",
)

st.title("🏉 HRFC Match-Day Pitch Map Generator")


@st.cache_data
def load_config_keys():
    if not CONFIG_PATH.exists():
        return []
    df = pd.read_excel(CONFIG_PATH, sheet_name=0)
    return df["pitch_key"].dropna().astype(str).tolist()


pitch_keys = load_config_keys()

tab_single, tab_batch = st.tabs(["Single Fixture", "Batch Processing"])

# ---------------------------------------------------------
# TAB 1: Single Fixture Mode
# ---------------------------------------------------------
with tab_single:
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("Fixture Parameters")

        pitch_choice = st.selectbox("Select Pitch Allocation", options=pitch_keys)

        home_team = st.text_input("Home Team", value="WARRIORS U14")
        opponent = st.text_input("Opponent Name", value="Cotswold Lionesses")

        c_time, c_date = st.columns(2)
        with c_time:
            ko_time = st.text_input("Kick-Off Time", value="13:00")
        with c_date:
            match_date = st.text_input("Match Date", value="19.04.26")

        is_provisional = st.checkbox("Mark as PROVISIONAL", value=False)

        run_single = st.button("Generate Pitch Map", type="primary", use_container_width=True)

    with col2:
        st.subheader("Map Preview")

        if run_single:
            with st.spinner("Rendering visual asset..."):
                try:
                    out_name = f"preview_{pitch_choice}_{home_team.replace(' ', '_')}.png"
                    output_path = generate_pitch_map(
                        config_excel_path=CONFIG_PATH,
                        pitch_key=pitch_choice,
                        home_team=home_team,
                        opponent=opponent,
                        ko_time=ko_time,
                        match_date=match_date,
                        is_provisional=is_provisional,
                        output_filename=out_name,
                    )

                    preview_img = Image.open(output_path)
                    st.image(preview_img, use_container_width=True)

                    with open(output_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Generated Map",
                            data=f.read(),
                            file_name=out_name,
                            mime="image/png",
                            use_container_width=True,
                        )
                except Exception as e:
                    st.error(f"Error generating map: {e}")
        else:
            st.info("Set the parameters on the left and click **Generate Pitch Map** to see the preview.")

# ---------------------------------------------------------
# TAB 2: Batch Processing Mode
# ---------------------------------------------------------
with tab_batch:
    st.subheader("Bulk Fixtures Upload")
    st.markdown(
        "Upload an Excel (`.xlsx`) or CSV file containing columns: `pitch_key`, `home_team`, `opponent`, `ko_time`, `match_date`, `is_provisional` (optional), `output_filename` (optional)."
    )

    uploaded_file = st.file_uploader("Upload Fixtures Sheet", type=["xlsx", "csv"])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                batch_df = pd.read_csv(uploaded_file)
            else:
                batch_df = pd.read_excel(uploaded_file)

            st.write("### Fixture Schedule Preview")
            st.dataframe(batch_df, use_container_width=True)

            if st.button("Generate All Maps (ZIP)", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()

                zip_buffer = io.BytesIO()
                total = len(batch_df)

                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for idx, row in batch_df.iterrows():
                        status_text.text(f"Processing fixture {idx + 1} of {total}: {row.get('home_team')} vs {row.get('opponent')}")

                        out_name = str(row.get("output_filename", "")).strip()
                        if not out_name or out_name.lower() == "nan":
                            h_safe = "".join(c for c in str(row["home_team"]) if c.isalnum() or c in ("_", "-"))
                            p_safe = "".join(c for c in str(row["pitch_key"]) if c.isalnum() or c in ("_", "-"))
                            out_name = f"map_{p_safe}_{h_safe}.png"

                        is_prov = False
                        if "is_provisional" in row and pd.notna(row["is_provisional"]):
                            is_prov = str(row["is_provisional"]).strip().upper() in ["TRUE", "1", "YES"]

                        out_file_path = generate_pitch_map(
                            config_excel_path=CONFIG_PATH,
                            pitch_key=str(row["pitch_key"]),
                            home_team=str(row["home_team"]),
                            opponent=str(row["opponent"]),
                            ko_time=str(row["ko_time"]),
                            match_date=str(row["match_date"]),
                            is_provisional=is_prov,
                            output_filename=out_name,
                        )

                        zip_file.write(out_file_path, arcname=out_name)
                        progress_bar.progress((idx + 1) / total)

                status_text.success(f"Generated {total} pitch maps successfully!")

                st.download_button(
                    label="⬇️ Download All Maps (.ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="pitch_maps_bundle.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
        except Exception as e:
            st.error(f"Error processing batch file: {e}")