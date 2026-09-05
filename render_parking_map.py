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

CANVA_DESIGN_WIDTH = 1920.0

PARKING_OPP_CX = 698.8
PARKING_OPP_CY = 980.05
PARKING_OPP_W = 171.2
PARKING_OPP_H = 160.9

PARKING_COMP_CX = 698.8
PARKING_COMP_CY = 740.0
PARKING_COMP_W = 144.7
PARKING_COMP_H = 144.7


def get_team_prefix(home_team: str) -> str:
    clean = str(home_team).strip().upper()
    if "WARRIOR" in clean:
        return "WARRIORS"
    if "HURRICANE" in clean:
        return "HURRICANES"
    return "DEFAULT"


@lru_cache(maxsize=8)
def get_cached_image(image_path_str: str) -> Image.Image:
    return Image.open(image_path_str).convert("RGBA")


def get_parking_base_path(home_team: str) -> Path:
    prefix = get_team_prefix(home_team)

    stems = [
        f"PARKING_HRFC_{prefix}",
        f"PARKING_{prefix}",
    ]

    for stem in stems:
        for ext in [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG"]:
            candidate = PARKING_MAPS_DIR / f"{stem}{ext}"
            if candidate.exists():
                return candidate

        for ext in [".png", ".PNG", ".jpg", ".JPG"]:
            candidate = ASSETS_DIR / f"{stem}{ext}"
            if candidate.exists():
                return candidate

    raise FileNotFoundError(f"Parking base map not found for stems {stems} in {PARKING_MAPS_DIR}")


@lru_cache(maxsize=64)
def load_opponent_crest(crest_stem: str, max_w_px: int, max_h_px: int) -> Image.Image | None:
    raw_name = crest_stem.strip()
    candidates = [
        OPPOSITIONS_DIR / f"{raw_name}_WHITE.png",
        OPPOSITIONS_DIR / f"{raw_name.replace(' ', '_')}_WHITE.png",
        OPPOSITIONS_DIR / f"{raw_name.upper()}_WHITE.png",
        OPPOSITIONS_DIR / f"{raw_name}.png",
        OPPOSITIONS_DIR / f"{raw_name.replace(' ', '_')}.png",
        OPPOSITIONS_DIR / f"{raw_name.upper()}.png",
    ]
    for path in candidates:
        if path.exists():
            img = Image.open(path).convert("RGBA")
            img.thumbnail((max_w_px, max_h_px), Image.Resampling.LANCZOS)
            return img
    return None


@lru_cache(maxsize=32)
def load_competition_logo(comp_code: str | None, max_w_px: int, max_h_px: int) -> Image.Image | None:
    if not comp_code or pd.isna(comp_code):
        return None

    clean_stem = str(comp_code).strip()
    clean_stem = re.sub(r"\.(png|jpg|jpeg)$", "", clean_stem, flags=re.IGNORECASE)
    if not clean_stem or clean_stem.upper() in ["NONE", "FRIENDLY", "NAN"]:
        return None

    candidates = [
        clean_stem,
        clean_stem.upper(),
        clean_stem.replace(" ", "_"),
        clean_stem.replace(" ", "_").upper(),
        clean_stem.replace(" ", ""),
        clean_stem.replace(" ", "").upper(),
    ]

    for stem in candidates:
        for ext in [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG"]:
            candidate = COMP_LOGOS_DIR / f"{stem}{ext}"
            if candidate.exists():
                img = Image.open(candidate).convert("RGBA")
                img.thumbnail((max_w_px, max_h_px), Image.Resampling.LANCZOS)
                return img

    return None


def generate_parking_map(
    home_team: str,
    opponent: str,
    opponent_crest_stem: str | None = None,
    competition: str | None = None,
    output_filename: str = "output_parking_map.png",
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base_path = get_parking_base_path(home_team)
    base_img = get_cached_image(str(base_path.resolve())).copy()
    scale = base_img.width / CANVA_DESIGN_WIDTH if base_img.width >= 1200 else base_img.height / 1080.0

    # 1. Opponent Crest
    opp_w = int(round(PARKING_OPP_W * scale))
    opp_h = int(round(PARKING_OPP_H * scale))
    lookup_name = opponent_crest_stem if opponent_crest_stem else opponent
    crest_img = load_opponent_crest(lookup_name, opp_w, opp_h)

    if crest_img:
        cx = PARKING_OPP_CX * scale
        cy = PARKING_OPP_CY * scale
        dest_x = int(round(cx - (crest_img.width / 2.0)))
        dest_y = int(round(cy - (crest_img.height / 2.0)))
        base_img.alpha_composite(crest_img, dest=(dest_x, dest_y))

    # 2. Competition Logo
    if competition:
        comp_w = int(round(PARKING_COMP_W * scale))
        comp_h = int(round(PARKING_COMP_H * scale))
        comp_img = load_competition_logo(competition, comp_w, comp_h)
        if comp_img:
            cx = PARKING_COMP_CX * scale
            cy = PARKING_COMP_CY * scale
            dest_x = int(round(cx - (comp_img.width / 2.0)))
            dest_y = int(round(cy - (comp_img.height / 2.0)))
            base_img.alpha_composite(comp_img, dest=(dest_x, dest_y))

    output_filepath = OUTPUT_DIR / output_filename
    base_img.save(output_filepath, "PNG")
    return output_filepath