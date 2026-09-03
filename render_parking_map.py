from pathlib import Path
from functools import lru_cache
import re
import pandas as pd
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
PARKING_MAPS_DIR = ASSETS_DIR / "parking_maps"
OPPOSITIONS_DIR = ASSETS_DIR / "oppositions"
COMP_LOGOS_DIR = ASSETS_DIR / "comp_logos"
OUTPUT_DIR = BASE_DIR / "output"

CANVA_DESIGN_WIDTH = 790.0

# Exact Canva bounding box from layout specification
OPPONENT_BOX_W = 171.2
OPPONENT_BOX_H = 160.9
PARKING_OPP_CX = 613.2 + (OPPONENT_BOX_W / 2.0)  # 698.8
PARKING_OPP_CY = 899.6 + (OPPONENT_BOX_H / 2.0)  # 980.05

# Competition logo stacked vertically above the opposition bounding box
PARKING_COMP_CX = PARKING_OPP_CX
PARKING_COMP_CY = 740.0


@lru_cache(maxsize=16)
def get_cached_base_image(image_path_str: str) -> Image.Image:
    return Image.open(image_path_str).convert("RGBA")


@lru_cache(maxsize=32)
def load_competition_logo(comp_code: str | None, max_w_px: int, max_h_px: int) -> Image.Image | None:
    if not comp_code or pd.isna(comp_code):
        return None

    clean_code = str(comp_code).strip()
    if not clean_code or clean_code.upper() in ["NONE", "FRIENDLY", "NAN"]:
        return None

    for ext in [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG"]:
        candidate = COMP_LOGOS_DIR / f"{clean_code}{ext}"
        if candidate.exists():
            img = Image.open(candidate).convert("RGBA")
            img.thumbnail((max_w_px, max_h_px), Image.Resampling.LANCZOS)
            return img

    return None


@lru_cache(maxsize=64)
def load_opponent_crest(crest_stem: str, max_w_px: int, max_h_px: int) -> Image.Image | None:
    raw_name = crest_stem.strip()
    base_name = re.sub(
        r"\b(RFC|RUFC|WRFC|U\d+|WARRIORS|HURRICANES|BOYS|GIRLS)\b",
        "",
        raw_name,
        flags=re.IGNORECASE,
    ).strip()

    search_terms = {raw_name, base_name}
    white_candidates = []
    standard_candidates = []

    for term in search_terms:
        if not term:
            continue
        underscored = term.replace(" ", "_")
        hyphenated = term.replace(" ", "-")

        white_candidates.extend(
            [
                OPPOSITIONS_DIR / f"{term}_WHITE.png",
                OPPOSITIONS_DIR / f"{underscored}_WHITE.png",
                OPPOSITIONS_DIR / f"{hyphenated}_WHITE.png",
                OPPOSITIONS_DIR / f"{term.upper()}_WHITE.png",
                OPPOSITIONS_DIR / f"{underscored.upper()}_WHITE.png",
            ]
        )
        standard_candidates.extend(
            [
                OPPOSITIONS_DIR / f"{term}.png",
                OPPOSITIONS_DIR / f"{underscored}.png",
                OPPOSITIONS_DIR / f"{hyphenated}.png",
                OPPOSITIONS_DIR / f"{term.upper()}.png",
                OPPOSITIONS_DIR / f"{underscored.upper()}.png",
                OPPOSITIONS_DIR / f"{term.lower()}.png",
                OPPOSITIONS_DIR / f"{underscored.lower()}.png",
            ]
        )

    for path in white_candidates + standard_candidates:
        if path.exists():
            img = Image.open(path).convert("RGBA")
            img.thumbnail((max_w_px, max_h_px), Image.Resampling.LANCZOS)
            return img

    return None


def get_parking_base_path(home_team: str) -> Path:
    clean = str(home_team).strip().upper()
    if "WARRIOR" in clean:
        stem = "PARKING_HRFC_WARRIORS"
    elif "HURRICANE" in clean:
        stem = "PARKING_HRFC_HURRICANES"
    else:
        stem = "PARKING_HRFC_DEFAULT"

    for ext in [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG"]:
        candidate = PARKING_MAPS_DIR / f"{stem}{ext}"
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"Parking base map image not found for stem: {stem} in {PARKING_MAPS_DIR}")


def generate_parking_map(
    home_team: str,
    opponent: str,
    opponent_crest_stem: str | None = None,
    competition: str | None = None,
    output_filename: str = "output_parking_map.png",
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base_image_path = get_parking_base_path(home_team)
    base_img = get_cached_base_image(str(base_image_path.resolve())).copy()
    scale = base_img.width / CANVA_DESIGN_WIDTH

    max_w = int(round(OPPONENT_BOX_W * scale))
    max_h = int(round(OPPONENT_BOX_H * scale))

    # Competition Logo
    if competition:
        comp_img = load_competition_logo(competition, max_w, max_h)
        if comp_img:
            comp_cx = PARKING_COMP_CX * scale
            comp_cy = PARKING_COMP_CY * scale
            comp_dest_x = int(round(comp_cx - (comp_img.width / 2.0)))
            comp_dest_y = int(round(comp_cy - (comp_img.height / 2.0)))
            base_img.alpha_composite(comp_img, dest=(comp_dest_x, comp_dest_y))

    # Opposition Crest
    lookup_name = opponent_crest_stem if opponent_crest_stem else opponent
    crest_img = load_opponent_crest(lookup_name, max_w, max_h)

    if crest_img:
        cx = PARKING_OPP_CX * scale
        cy = PARKING_OPP_CY * scale
        dest_x = int(round(cx - (crest_img.width / 2.0)))
        dest_y = int(round(cy - (crest_img.height / 2.0)))
        base_img.alpha_composite(crest_img, dest=(dest_x, dest_y))

    output_filepath = OUTPUT_DIR / output_filename
    base_img.convert("RGB").save(output_filepath, "PNG")

    return output_filepath


def process_parking_batch(fixtures_excel_path: Path):
    df = pd.read_excel(fixtures_excel_path)
    for _, row in df.iterrows():
        out_name = str(row.get("parking_output_filename", "")).strip()
        if not out_name or out_name.lower() == "nan":
            safe_team = re.sub(r"[^A-Za-z0-9]", "_", str(row["home_team"]))
            safe_opp = re.sub(r"[^A-Za-z0-9]", "_", str(row["opponent"]))
            out_name = f"parking_map_{safe_team}_v_{safe_opp}.png"

        crest_stem = (
            str(row["opponent_crest_stem"]).strip()
            if "opponent_crest_stem" in row and pd.notna(row["opponent_crest_stem"])
            else None
        )
        comp = (
            str(row["competition"]).strip()
            if "competition" in row and pd.notna(row["competition"])
            else None
        )

        generate_parking_map(
            home_team=str(row["home_team"]),
            opponent=str(row["opponent"]),
            opponent_crest_stem=crest_stem,
            competition=comp,
            output_filename=out_name,
        )


if __name__ == "__main__":
    generate_parking_map(
        home_team="WARRIORS U14",
        opponent="BRACKNELL RFC",
        opponent_crest_stem="BRACKNELL",
        competition="U16GIRLSNATCUP",
        output_filename="test_parking_calibrated.png",
    )