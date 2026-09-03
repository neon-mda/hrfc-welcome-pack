from pathlib import Path
import datetime
import io
import zipfile
import pandas as pd
import streamlit as st
from PIL import Image

from render_pitch_map import (
    BASE_DIR,
    OUTPUT_DIR,
    generate_pitch_map,
)

CONFIG_PATH = BASE_DIR / "config.xlsx"

st.set_page_config(
    page_title="HRFC Pitch Map Generator",
    page_icon="🏉",
    layout="wide",
)

st.title("🏉 HRFC Match-Day Pitch Map Generator")

TEAM_OPTIONS = [
    "U13",
    "U14",
    "HURRICANES",
    "COLTS",
    "WARRIORS U12",
    "WARRIORS U14",
    "WARRIORS U16",
    "U12",
    "U11",
    "U10",
    "U9",
    "U8",
    "U7",
    "U6",
    "OTHER (CUSTOM...)",
]

COMPETITION_LABELS = {
    "None": "None",
    "HOB": "HOB",
    "BYC": "BYC",
    "BKO": "Berks KO Cup",
    "U16GIRLSNATCUP": "Girls National Cup",
    "PUP": "PUP",
    "OBB": "OBB",
}


def get_next_sunday(today: datetime.date | None = None) -> datetime.date:
    current = today or datetime.date.today()
    # Monday is 0 and Sunday is 6
    days_until_sunday = (6 - current.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    return current + datetime.timedelta(days=days_until_sunday)


@st.cache_data
def load_config_keys():
    if not CONFIG_PATH.exists():
        return []
    df = pd.read_excel(CONFIG_PATH, sheet_name=0)
    return df["pitch_key"].dropna().astype(str).tolist()


@st.cache_data
def load_opponents_data():
    if not CONFIG_PATH.exists():
        return {}
    try:
        df = pd.read_excel(CONFIG_PATH, sheet_name="opponents")
        opp_dict = {}
        for _, row in df.iterrows():
            d_name = str(row["display_name"]).strip()
            alias = str(row["alias"]).strip() if pd.notna(row.get("alias")) else d_name
            stem = str(row["crest_asset_stem"]).strip() if pd.notna(row.get("crest_asset_stem")) else d_name
            opp_dict[d_name.upper()] = {"alias": alias, "crest_stem": stem, "original_display": d_name}
        return opp_dict
    except Exception:
        return {}


@st.cache_data
def load_available_logos():
    comp_dir = BASE_DIR / "assets" / "comp_logos"
    if not comp_dir.exists():
        return set()
    return {f.stem.upper() for f in comp_dir.glob("*.png")}


def get_competitions_for_team(team_name: str, available_logos: set[str]) -> list[str]:
    clean_team = str(team_name).strip().upper()

    if clean_team == "WARRIORS U12":
        allowed = ["PUP"]
    elif clean_team == "WARRIORS U14":
        allowed = ["BKO", "HOB", "PUP"]
    elif clean_team == "WARRIORS U16":
        allowed = ["HOB", "U16GIRLSNATCUP"]
    elif clean_team in ["HURRICANES", "COLTS"]:
        allowed = ["OBB"]
    elif clean_team in ["U13", "U14"]:
        allowed = ["BKO", "BYC"]
    elif "WARRIORS" in clean_team:
        allowed = ["BKO", "HOB", "PUP", "U16GIRLSNATCUP"]
    else:
        allowed = []

    valid_codes = [c for c in allowed if c in available_logos]
    return ["None"] + valid_codes


pitch_keys = load_config_keys()
available_logos = load_available_logos()
opponents_data = load_opponents_data()

tab_single, tab_batch = st.tabs(["Single Fixture", "Batch Processing"])

# ---------------------------------------------------------
# TAB 1: Single Fixture Mode
# ---------------------------------------------------------
with tab_single:
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("Fixture Parameters")

        pitch_choice = st.selectbox("Select Pitch Allocation", options=pitch_keys)

        selected_team = st.selectbox(
            "Home Team",
            options=TEAM_OPTIONS,
            index=5,  # WARRIORS U14
        )

        if selected_team == "OTHER (CUSTOM...)":
            home_team = st.text_input("Enter Custom Team Name", value="")
        else:
            home_team = selected_team

        opp_options = sorted(list(opponents_data.keys())) + ["OTHER (CUSTOM...)"]
        selected_opp = st.selectbox("Opponent", options=opp_options, index=0 if opp_options else 0)

        if selected_opp == "OTHER (CUSTOM...)":
            opponent_display = st.text_input("Enter Custom Opponent Name", value="").strip().upper()
            opponent_alias = opponent_display
            opponent_crest_stem = opponent_display
        else:
            opponent_display = selected_opp
            opponent_alias = opponents_data[selected_opp]["alias"]
            opponent_crest_stem = opponents_data[selected_opp]["crest_stem"]

        c_time, c_date = st.columns(2)
        with c_time:
            picked_time = st.time_input(
                "Kick-Off Time",
                value=datetime.time(10, 0),
                step=datetime.timedelta(minutes=15),
            )
            ko_time = picked_time.strftime("%H:%M")

        with c_date:
            next_sunday = get_next_sunday()
            picked_date = st.date_input(
                "Match Date",
                value=next_sunday,
                format="DD/MM/YYYY",
            )
            match_date = picked_date.strftime("%d.%m.%y")

        comp_codes = get_competitions_for_team(home_team, available_logos)
        selected_code = st.selectbox(
            "Competition",
            options=comp_codes,
            format_func=lambda code: COMPETITION_LABELS.get(code, code),
            help="Competitions filtered by the selected team",
        )
        comp_arg = None if selected_code == "None" else selected_code

        is_provisional = st.checkbox("Mark as PROVISIONAL", value=False)

        run_single = st.button("Generate Pitch Map", type="primary", use_container_width=True)

    with col2:
        st.subheader("Map Preview")

        if run_single:
            with st.spinner("Rendering visual asset..."):
                try:
                    h_clean = "".join(c for c in home_team if c.isalnum() or c in ("_", "-"))
                    p_clean = "".join(c for c in pitch_choice if c.isalnum() or c in ("_", "-"))
                    out_name = f"preview_{p_clean}_{h_clean}.png"

                    output_path = generate_pitch_map(
                        config_excel_path=CONFIG_PATH,
                        pitch_key=pitch_choice,
                        home_team=home_team,
                        opponent=opponent_display,
                        ko_time=ko_time,
                        opponent_alias=opponent_alias,
                        opponent_crest_stem=opponent_crest_stem,
                        match_date=match_date,
                        is_provisional=is_provisional,
                        competition=comp_arg,
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
        "Upload an Excel (`.xlsx`) or CSV file containing columns: `pitch_key`, `home_team`, `opponent`, `ko_time`, `match_date`, `competition` (optional), `is_provisional` (optional), `output_filename` (optional)."
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

                        comp = str(row["competition"]).strip() if "competition" in row and pd.notna(row["competition"]) else None

                        opp_raw = str(row["opponent"]).strip().upper()
                        meta = opponents_data.get(opp_raw, {})
                        opp_alias = meta.get("alias", opp_raw)
                        opp_stem = meta.get("crest_stem", opp_raw)

                        out_file_path = generate_pitch_map(
                            config_excel_path=CONFIG_PATH,
                            pitch_key=str(row["pitch_key"]),
                            home_team=str(row["home_team"]),
                            opponent=opp_raw,
                            ko_time=str(row["ko_time"]),
                            opponent_alias=opp_alias,
                            opponent_crest_stem=opp_stem,
                            match_date=str(row["match_date"]),
                            is_provisional=is_prov,
                            competition=comp,
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