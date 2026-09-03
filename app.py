from pathlib import Path
from datetime import date, timedelta
import io
import re
import zipfile
import pandas as pd
import streamlit as st

from render_pitch_map import generate_pitch_map, get_cached_config_dfs
from render_parking_map import generate_parking_map
from render_front_cover import generate_front_cover

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.xlsx"
ASSETS_DIR = BASE_DIR / "assets"
OPPOSITIONS_DIR = ASSETS_DIR / "oppositions"
OUTPUT_DIR = BASE_DIR / "output"

st.set_page_config(
    page_title="HRFC Match-Day Asset Generator",
    page_icon="🏉",
    layout="wide",
)


def get_next_sunday() -> date:
    today = date.today()
    days_ahead = 6 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def get_config_mtime() -> float:
    return CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else 0.0


@st.cache_data
def load_base_metadata(mtime: float):
    anchors_df, _ = get_cached_config_dfs(CONFIG_PATH)
    pitch_keys = anchors_df["pitch_key"].dropna().unique().tolist()

    opponents_df = pd.DataFrame()
    opponents = []
    try:
        opponents_df = pd.read_excel(CONFIG_PATH, sheet_name="opponents")

        name_col = next(
            (
                c
                for c in opponents_df.columns
                if str(c).strip().lower() in ["display_name", "displayname", "display"]
            ),
            None,
        )
        if not name_col:
            name_col = next(
                (
                    c
                    for c in opponents_df.columns
                    if str(c).strip().lower() in ["opponent", "club", "team"]
                ),
                None,
            )

        if name_col:
            opponents = [
                str(x).strip().upper()
                for x in opponents_df[name_col].dropna().unique().tolist()
                if str(x).strip() and str(x).strip().upper() != "NAN"
            ]
    except Exception as e:
        st.warning(f"Could not read opponents sheet: {e}")

    if not opponents and OPPOSITIONS_DIR.exists():
        for file in sorted(OPPOSITIONS_DIR.iterdir()):
            if file.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                stem = re.sub(r"_WHITE$", "", file.stem, flags=re.IGNORECASE).strip().upper()
                if stem and stem not in opponents:
                    opponents.append(stem)

    opponents = sorted(list(set(opponents)))

    comps_df = pd.DataFrame()
    ordered_teams = []
    try:
        comps_df = pd.read_excel(CONFIG_PATH, sheet_name="comps")
        comps_df["list_sort"] = pd.to_numeric(comps_df["list_sort"], errors="coerce").fillna(999)
        sorted_comps = comps_df.sort_values(by="list_sort")
        for t in sorted_comps["team_key"].dropna().astype(str).str.strip():
            if t and t not in ordered_teams:
                ordered_teams.append(t)
    except Exception as e:
        st.warning(f"Could not read comps sheet: {e}")

    return pitch_keys, opponents, opponents_df, comps_df, ordered_teams


def get_competitions_for_team(team_key: str, comps_df: pd.DataFrame) -> tuple[list[str], dict[str, str]]:
    options = ["NONE"]
    alias_to_code_map = {"NONE": None}

    if comps_df.empty or "team_key" not in comps_df.columns:
        return options, alias_to_code_map

    matched = comps_df[comps_df["team_key"].astype(str).str.strip() == str(team_key).strip()]

    for _, row in matched.iterrows():
        comp_alias_raw = row.get("comp_alias")
        comp_name_raw = row.get("comp_name")

        if pd.notna(comp_alias_raw):
            alias_upper = str(comp_alias_raw).strip().upper()
            if alias_upper and alias_upper not in ["NONE", "NAN", "FRIENDLY"]:
                code_str = str(comp_name_raw).strip() if pd.notna(comp_name_raw) else alias_upper
                if alias_upper not in options:
                    options.append(alias_upper)
                    alias_to_code_map[alias_upper] = code_str

    return options, alias_to_code_map


pitch_keys, opponent_list, opponents_meta_df, comps_df, home_team_options = load_base_metadata(
    get_config_mtime()
)

st.title("🏉 HRFC Match-Day Asset Generator")

mode = st.radio(
    "Mode",
    ["Single Fixture", "Batch Processing"],
    horizontal=True,
    label_visibility="collapsed",
)

if mode == "Single Fixture":
    col_params, col_preview = st.columns([1, 1], gap="large")

    with col_params:
        st.subheader("Fixture Parameters")

        selected_pitch = st.selectbox(
            "Select Pitch Allocation",
            options=pitch_keys,
            index=0 if pitch_keys else None,
        )

        home_team = st.selectbox(
            "Home Team",
            options=home_team_options if home_team_options else ["WARRIORS U16"],
            index=0,
        )

        opponent = st.selectbox(
            "Opponent",
            options=opponent_list if opponent_list else ["ABBEY RFC"],
            index=0,
        )

        col_ko, col_date = st.columns(2)
        with col_ko:
            ko_time = st.text_input("Kick-Off Time", value="10:00")
        with col_date:
            match_date_val = st.date_input(
                "Match Date",
                value=get_next_sunday(),
                format="DD/MM/YYYY",
            )
            match_date_str = match_date_val.strftime("%d %b %Y").upper()
            st.caption(f"Formatted: **{match_date_str}**")

        col_ref, col_comp = st.columns(2)
        with col_ref:
            referee = st.text_input("Referee", value="TBC")

        with col_comp:
            comp_options, alias_to_code_map = get_competitions_for_team(home_team, comps_df)
            selected_alias = st.selectbox(
                "Competition",
                options=comp_options,
                index=0,
            )
            comp_code = alias_to_code_map.get(selected_alias, None)

        is_provisional = st.checkbox("Mark as PROVISIONAL", value=False)

        opp_alias = None
        opp_crest = None
        if not opponents_meta_df.empty:
            lookup_col = next(
                (
                    c
                    for c in opponents_meta_df.columns
                    if str(c).strip().lower() in ["display_name", "displayname", "display", "opponent"]
                ),
                None,
            )
            if lookup_col:
                matched_opp = opponents_meta_df[
                    opponents_meta_df[lookup_col].astype(str).str.strip().str.upper() == str(opponent).strip().upper()
                ]
                if not matched_opp.empty:
                    row = matched_opp.iloc[0]
                    alias_col = next((c for c in opponents_meta_df.columns if "alias" in str(c).lower()), None)
                    crest_col = next((c for c in opponents_meta_df.columns if "crest" in str(c).lower()), None)

                    if alias_col and pd.notna(row[alias_col]):
                        opp_alias = str(row[alias_col]).strip()
                    if crest_col and pd.notna(row[crest_col]):
                        opp_crest = str(row[crest_col]).strip()

        generate_btn = st.button("Generate Assets", type="primary", use_container_width=True)

    with col_preview:
        st.subheader("Asset Preview")

        if generate_btn:
            with st.spinner("Generating graphics..."):
                cover_path = generate_front_cover(
                    home_team=home_team,
                    opponent=opponent,
                    ko_time=ko_time,
                    match_date=match_date_str,
                    referee=referee,
                    opponent_crest_stem=opp_crest,
                    competition=comp_code,
                    output_filename="preview_front_cover.png",
                )

                pitch_path = generate_pitch_map(
                    config_excel_path=CONFIG_PATH,
                    pitch_key=selected_pitch,
                    home_team=home_team,
                    opponent=opponent,
                    ko_time=ko_time,
                    opponent_alias=opp_alias,
                    opponent_crest_stem=opp_crest,
                    match_date=match_date_str,
                    is_provisional=is_provisional,
                    competition=comp_code,
                    output_filename="preview_pitch_map.png",
                )

                parking_path = generate_parking_map(
                    home_team=home_team,
                    opponent=opponent,
                    opponent_crest_stem=opp_crest,
                    competition=comp_code,
                    output_filename="preview_parking_map.png",
                )

                st.session_state["cover_img"] = cover_path
                st.session_state["pitch_img"] = pitch_path
                st.session_state["parking_img"] = parking_path

        tab_cover, tab_pitch, tab_parking = st.tabs(["📖 Front Cover", "🏟️ Pitch Map", "🚗 Parking Map"])

        with tab_cover:
            if "cover_img" in st.session_state and Path(st.session_state["cover_img"]).exists():
                st.image(str(st.session_state["cover_img"]), use_container_width=True)
                with open(st.session_state["cover_img"], "rb") as f:
                    st.download_button(
                        label="Download Front Cover",
                        data=f,
                        file_name=f"cover_{home_team}_v_{opponent}.png".replace(" ", "_"),
                        mime="image/png",
                        use_container_width=True,
                    )
            else:
                st.info("Click 'Generate Assets' to preview the Front Cover.")

        with tab_pitch:
            if "pitch_img" in st.session_state and Path(st.session_state["pitch_img"]).exists():
                st.image(str(st.session_state["pitch_img"]), use_container_width=True)
                with open(st.session_state["pitch_img"], "rb") as f:
                    st.download_button(
                        label="Download Pitch Map",
                        data=f,
                        file_name=f"pitch_map_{home_team}_{selected_pitch}.png".replace(" ", "_"),
                        mime="image/png",
                        use_container_width=True,
                    )
            else:
                st.info("Click 'Generate Assets' to preview the Pitch Map.")

        with tab_parking:
            if "parking_img" in st.session_state and Path(st.session_state["parking_img"]).exists():
                st.image(str(st.session_state["parking_img"]), use_container_width=True)
                with open(st.session_state["parking_img"], "rb") as f:
                    st.download_button(
                        label="Download Parking Map",
                        data=f,
                        file_name=f"parking_map_{home_team}_v_{opponent}.png".replace(" ", "_"),
                        mime="image/png",
                        use_container_width=True,
                    )
            else:
                st.info("Click 'Generate Assets' to preview the Parking Map.")

else:
    st.subheader("Batch Processing")
    uploaded_file = st.file_uploader("Upload Fixtures Spreadsheet (.xlsx)", type=["xlsx"])

    if uploaded_file is not None:
        fixtures_df = pd.read_excel(uploaded_file)
        st.dataframe(fixtures_df.head(10), use_container_width=True)

        if st.button("Run Full Matchday Batch", type="primary"):
            zip_buffer = io.BytesIO()
            with st.spinner("Compiling full matchday packages..."):
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for idx, row in fixtures_df.iterrows():
                        team = str(row["home_team"])
                        opp = str(row["opponent"]).upper()
                        pkey = str(row["pitch_key"])
                        ko = str(row["ko_time"])
                        ref = str(row.get("referee", "TBC"))
                        mdate = str(row.get("match_date", get_next_sunday().strftime("%d %b %Y").upper()))
                        prov = str(row.get("is_provisional", "false")).strip().upper() in [
                            "TRUE",
                            "1",
                            "YES",
                        ]
                        raw_comp = (
                            str(row["competition"]).strip()
                            if "competition" in row and pd.notna(row["competition"])
                            else None
                        )
                        comp = (
                            None
                            if not raw_comp or raw_comp.upper() in ["NONE", "FRIENDLY", "NAN"]
                            else raw_comp
                        )
                        c_stem = (
                            str(row["opponent_crest_stem"]).strip()
                            if "opponent_crest_stem" in row and pd.notna(row["opponent_crest_stem"])
                            else None
                        )

                        clean_team = team.replace(" ", "_")
                        clean_opp = opp.replace(" ", "_")

                        c_file = f"cover_{clean_team}_v_{clean_opp}_{idx}.png"
                        c_path = generate_front_cover(
                            home_team=team,
                            opponent=opp,
                            ko_time=ko,
                            match_date=mdate,
                            referee=ref,
                            opponent_crest_stem=c_stem,
                            competition=comp,
                            output_filename=c_file,
                        )
                        zip_file.write(c_path, arcname=f"front_covers/{c_file}")

                        p_file = f"pitch_{clean_team}_{pkey}_{idx}.png"
                        p_path = generate_pitch_map(
                            config_excel_path=CONFIG_PATH,
                            pitch_key=pkey,
                            home_team=team,
                            opponent=opp,
                            ko_time=ko,
                            opponent_crest_stem=c_stem,
                            match_date=mdate,
                            is_provisional=prov,
                            competition=comp,
                            output_filename=p_file,
                        )
                        zip_file.write(p_path, arcname=f"pitch_maps/{p_file}")

                        park_file = f"parking_{clean_team}_v_{clean_opp}_{idx}.png"
                        park_path = generate_parking_map(
                            home_team=team,
                            opponent=opp,
                            opponent_crest_stem=c_stem,
                            competition=comp,
                            output_filename=park_file,
                        )
                        zip_file.write(park_path, arcname=f"parking_maps/{park_file}")

            st.success("Batch generation complete.")
            st.download_button(
                label="Download Matchday Pack (.zip)",
                data=zip_buffer.getvalue(),
                file_name="HRFC_Matchday_Assets.zip",
                mime="application/zip",
                use_container_width=True,
            )