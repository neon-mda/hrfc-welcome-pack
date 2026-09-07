from pathlib import Path
from functools import lru_cache
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from render_parking_map import generate_parking_map

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.xlsx"
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
COVERS_DIR = ASSETS_DIR / "covers"
OUTPUT_DIR = BASE_DIR / "output"

CANVA_DESIGN_WIDTH = 1920.0

NOTES_BOX_X = 1083.1
NOTES_BOX_Y = 45.6
NOTES_BOX_W = 804.6
NOTES_BOX_H = 133.3
NOTES_FONT_PT = 20.0

DEFAULT_NOTES_TEXT = (
    "Please note the club is expected to be very busy this weekend. "
    "We kindly ask all visiting and home families to car-share wherever possible "
    "and follow the directions of our parking marshals."
)


def hex_to_rgba(hex_code: str, alpha: int = 255) -> tuple[int, int, int, int]:
    clean_hex = str(hex_code).lstrip("#").strip()
    if len(clean_hex) == 3:
        clean_hex = "".join([c * 2 for c in clean_hex])
    if len(clean_hex) != 6:
        return (30, 30, 30, alpha)
    r = int(clean_hex[0:2], 16)
    g = int(clean_hex[2:4], 16)
    b = int(clean_hex[4:6], 16)
    return (r, g, b, alpha)


def get_team_prefix(home_team: str) -> str:
    clean = str(home_team).strip().upper()
    if "WARRIOR" in clean:
        return "WARRIORS"
    if "HURRICANE" in clean:
        return "HURRICANES"
    return "DEFAULT"


@lru_cache(maxsize=4)
def get_cached_teams_df(config_excel_path_str: str) -> pd.DataFrame:
    try:
        return pd.read_excel(config_excel_path_str, sheet_name="teams")
    except Exception:
        return pd.DataFrame()


def get_text_info_color(home_team: str) -> tuple[int, int, int, int]:
    prefix = get_team_prefix(home_team)
    default_rgba = (30, 30, 30, 255)

    if CONFIG_PATH.exists():
        teams_df = get_cached_teams_df(str(CONFIG_PATH.resolve()))
        if not teams_df.empty and "team_prefix" in teams_df.columns:
            lookup_prefix = "DEFAULT" if prefix == "HURRICANES" else prefix
            matched = teams_df[teams_df["team_prefix"].astype(str).str.strip().str.upper() == lookup_prefix]
            if not matched.empty:
                row = matched.iloc[0]
                if "text_info" in row and pd.notna(row["text_info"]):
                    return hex_to_rgba(str(row["text_info"]).strip())

            if lookup_prefix != "DEFAULT":
                def_matched = teams_df[teams_df["team_prefix"].astype(str).str.strip().str.upper() == "DEFAULT"]
                if not def_matched.empty:
                    def_row = def_matched.iloc[0]
                    if "text_info" in def_row and pd.notna(def_row["text_info"]):
                        return hex_to_rgba(str(def_row["text_info"]).strip())

    return default_rgba


@lru_cache(maxsize=8)
def get_cached_base_image(image_path_str: str) -> Image.Image:
    return Image.open(image_path_str).convert("RGBA")


@lru_cache(maxsize=64)
def get_cached_font(font_path_str: str, size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path_str, size=size_px)


def resolve_font_path(bold: bool = False) -> Path:
    target_name = "Poppins-Bold.ttf" if bold else "Poppins-Regular.ttf"
    font_path = FONTS_DIR / target_name
    if font_path.exists():
        return font_path

    alt_candidates = [
        FONTS_DIR / ("Aptos-Bold.ttf" if bold else "Aptos.ttf"),
        FONTS_DIR / "Poppins-Medium.ttf",
    ]
    for alt in alt_candidates:
        if alt.exists():
            return alt

    generic = list(FONTS_DIR.glob("*.ttf")) + list(FONTS_DIR.glob("*.otf"))
    return generic[0] if generic else Path()


def get_locnotes_base_path(home_team: str) -> Path:
    prefix = get_team_prefix(home_team)
    stem = f"LOCNOTES_{prefix}"

    for ext in [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG"]:
        candidate = COVERS_DIR / f"{stem}{ext}"
        if candidate.exists():
            return candidate

    for ext in [".png", ".PNG", ".jpg", ".JPG"]:
        candidate = ASSETS_DIR / f"{stem}{ext}"
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"LOCNOTES plate not found for stem: {stem}")


def wrap_text_to_width(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width_px: float,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_w = bbox[2] - bbox[0]

        if line_w <= max_width_px:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def generate_locnotes_page(
    home_team: str,
    opponent: str,
    opponent_crest_stem: str | None = None,
    competition: str | None = None,
    custom_notes: str | None = None,
    output_filename: str = "output_locnotes.png",
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Base Plate
    base_plate_path = get_locnotes_base_path(home_team)
    base_plate = get_cached_base_image(str(base_plate_path.resolve())).copy()
    scale = base_plate.width / CANVA_DESIGN_WIDTH

    # 2. Render and Composite Parking Map Overlay
    parking_map_path = generate_parking_map(
        home_team=home_team,
        opponent=opponent,
        opponent_crest_stem=opponent_crest_stem,
        competition=competition,
        output_filename="temp_parking_map_overlay.png",
    )
    parking_map = Image.open(parking_map_path).convert("RGBA")

    if parking_map.height != base_plate.height:
        ratio = base_plate.height / float(parking_map.height)
        new_w = int(round(parking_map.width * ratio))
        parking_map = parking_map.resize((new_w, base_plate.height), Image.Resampling.LANCZOS)

    base_plate.alpha_composite(parking_map, dest=(0, 0))

    # 3. Dynamic Text Block
    notes_text = custom_notes.strip() if custom_notes and custom_notes.strip() else DEFAULT_NOTES_TEXT
    text_color = get_text_info_color(home_team)

    txt_layer = Image.new("RGBA", base_plate.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_layer)

    path_reg = resolve_font_path(bold=False)
    font_size_px = int(round(NOTES_FONT_PT * scale))
    font_notes = get_cached_font(str(path_reg.resolve()), font_size_px)

    box_x = int(round(NOTES_BOX_X * scale))
    box_y = int(round(NOTES_BOX_Y * scale))
    box_w = NOTES_BOX_W * scale
    box_h = NOTES_BOX_H * scale

    wrapped_lines = wrap_text_to_width(notes_text, font_notes, box_w, draw)
    line_advance = int(round(NOTES_FONT_PT * 1.25 * scale))

    cur_y = box_y
    for line in wrapped_lines:
        if cur_y + line_advance > box_y + box_h + 10:
            break
        draw.text((box_x, cur_y), line, font=font_notes, fill=text_color)
        cur_y += line_advance

    base_plate.alpha_composite(txt_layer)

    output_filepath = OUTPUT_DIR / output_filename
    base_plate.convert("RGB").save(output_filepath, "PNG")

    return output_filepath