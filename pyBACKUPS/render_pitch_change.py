from pathlib import Path
from functools import lru_cache
from datetime import datetime
import math
import re
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MAPS_DIR = ASSETS_DIR / "maps"
COVERS_DIR = ASSETS_DIR / "covers"
BRANDING_DIR = ASSETS_DIR / "branding"
OPPOSITIONS_DIR = ASSETS_DIR / "oppositions"
OUTPUT_DIR = BASE_DIR / "output"

CANVA_DESIGN_WIDTH = 1920.0

CHANGING_ROOM_BOXES = {
    1: {"x": 1137.9, "y": 300.9, "w": 93.0, "h": 120.0},
    2: {"x": 1232.9, "y": 300.9, "w": 93.0, "h": 120.0},
    3: {"x": 1481.0, "y": 300.9, "w": 93.0, "h": 120.0},
    4: {"x": 1699.5, "y": 300.9, "w": 93.0, "h": 120.0},
}

@lru_cache(maxsize=16)
def get_cached_base_image(image_path_str: str) -> Image.Image:
    return Image.open(image_path_str).convert("RGBA")

@lru_cache(maxsize=64)
def get_cached_font(font_path_str: str, size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path_str, size=size_px)

def resolve_font_path(style: str = "Bold") -> Path:
    clean_style = str(style).strip().lower()
    if "regular" in clean_style:
        filename = "Poppins-Regular.ttf"
    else:
        filename = "Poppins-Bold.ttf"
    target = FONTS_DIR / filename
    if target.exists():
        return target
    fallbacks = [FONTS_DIR / "Poppins-Bold.ttf", FONTS_DIR / "Poppins-Regular.ttf"]
    for fb in fallbacks:
        if fb.exists():
            return fb
    generic = list(FONTS_DIR.glob("*.ttf"))
    return generic[0] if generic else Path()

@lru_cache(maxsize=64)
def load_club_crest(home_team: str, max_w_px: int, max_h_px: int) -> Image.Image | None:
    clean = str(home_team).strip().upper()
    prefix = "HUNGERFORD"
    if "WARRIOR" in clean:
        prefix = "WARRIORS"
    elif "HURRICANE" in clean:
        prefix = "HURRICANES"

    candidates = [
        BRANDING_DIR / f"{prefix}_CREST.png",
        BRANDING_DIR / f"{prefix}.png",
        BRANDING_DIR / "HUNGERFORD_CREST.png",
        BRANDING_DIR / "HRFC_CREST.png",
        BRANDING_DIR / "HRFC.png"
    ]
    for path in candidates:
        if path.exists():
            img = Image.open(path).convert("RGBA")
            img.thumbnail((max_w_px, max_h_px), Image.Resampling.LANCZOS)
            return img
    return None

@lru_cache(maxsize=64)
def load_opponent_crest(crest_stem: str, max_w_px: int, max_h_px: int) -> Image.Image | None:
    raw_name = crest_stem.strip()
    base_name = re.sub(r"\b(RFC|RUFC|WRFC|U\d+|WARRIORS|HURRICANES|BOYS|GIRLS)\b", "", raw_name, flags=re.IGNORECASE).strip()
    search_terms = {raw_name, base_name}
    candidates = []
    for term in search_terms:
        if not term:
            continue
        u = term.replace(" ", "_")
        candidates.extend([
            OPPOSITIONS_DIR / f"{term}.png",
            OPPOSITIONS_DIR / f"{u}.png",
            OPPOSITIONS_DIR / f"{term.upper()}.png",
            OPPOSITIONS_DIR / f"{u.upper()}.png",
        ])
    for path in candidates:
        if path.exists():
            img = Image.open(path).convert("RGBA")
            img.thumbnail((max_w_px, max_h_px), Image.Resampling.LANCZOS)
            return img
    return None

def resolve_template_path(home_team: str) -> Path:
    clean = str(home_team).strip().upper()
    prefix = "DEFAULT"
    if "WARRIOR" in clean:
        prefix = "WARRIORS"
    elif "HURRICANE" in clean:
        prefix = "HURRICANES"

    candidates = [
        COVERS_DIR / f"PITCHCHANGE_{prefix}.png",
        COVERS_DIR / "PITCHCHANGE_DEFAULT.png",
        COVERS_DIR / "PITCHCHANGE.png",
        MAPS_DIR / f"PITCHCHANGE_{prefix}.png",
        MAPS_DIR / "PITCHCHANGE.png",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Pitch change template not found for prefix '{prefix}' in covers or maps directory.")

def parse_color(val, default_color):
    if isinstance(val, str):
        val = val.strip()
        if val.startswith('#'):
            h = val.lstrip('#')
            try:
                rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                return rgb + (255,)
            except Exception:
                pass
        elif ',' in val:
            try:
                parts = [int(p.strip()) for p in val.split(',')]
                if len(parts) == 3:
                    return tuple(parts) + (255,)
                elif len(parts) == 4:
                    return tuple(parts)
            except Exception:
                pass
    return default_color

def get_team_colors(config_excel_path: Path, home_team: str) -> tuple[tuple[int,int,int,int], tuple[int,int,int,int]]:
    clean = str(home_team).strip().upper()
    if "WARRIOR" in clean:
        default_info = (172, 7, 83, 255)
    else:
        default_info = (130, 28, 52, 255)
    default_cr = (0, 0, 0, 255)

    try:
        if config_excel_path and config_excel_path.exists():
            df = pd.read_excel(config_excel_path, sheet_name="teams")
            team_col = next((c for c in df.columns if 'team' in str(c).lower() or 'key' in str(c).lower() or 'name' in str(c).lower()), None)
            if team_col:
                matched = df[df[team_col].astype(str).str.strip().str.upper() == clean]
                if not matched.empty:
                    row = matched.iloc[0]
                    info_col = next((c for c in df.columns if 'info' in str(c).lower()), None)
                    cr_col = next((c for c in df.columns if 'cr' in str(c).lower() or 'primary' in str(c).lower() or 'body' in str(c).lower()), None)

                    if info_col and pd.notna(row[info_col]):
                        default_info = parse_color(row[info_col], default_info)
                    if cr_col and pd.notna(row[cr_col]):
                        default_cr = parse_color(row[cr_col], default_cr)
    except Exception:
        pass

    return default_info, default_cr

def generate_pitch_change_map(
    config_excel_path: Path,
    home_team: str,
    opponent: str,
    home_room_num: int,
    away_room_num: int,
    in_time: str,
    out_time: str,
    category_title: str = "HRFC CHANGING ROOMS",
    home_crest_stem: str | None = None,
    away_crest_stem: str | None = None,
    pitch_map_path: Path | None = None,
    output_filename: str = "output_pitch_change.png",
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    template_path = resolve_template_path(home_team)

    text_info_color, text_cr_color = get_team_colors(config_excel_path, home_team)

    base_img = get_cached_base_image(str(template_path.resolve())).copy()
    scale = base_img.width / CANVA_DESIGN_WIDTH

    if pitch_map_path and Path(pitch_map_path).exists():
        pitch_img = Image.open(pitch_map_path).convert("RGBA")
        target_w = int(round(789.8 * scale))
        target_h = int(round(1080.0 * scale))
        pitch_img = pitch_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        base_img.paste(pitch_img, (0, 0), pitch_img)

    txt_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(txt_layer)

    font_bold_path = resolve_font_path("Bold")
    font_reg_path = resolve_font_path("Regular")

    title_font = get_cached_font(str(font_bold_path.resolve()), int(round(36.0 * scale)))
    room_text_font = get_cached_font(str(font_bold_path.resolve()), int(round(34.0 * scale)))
    room_num_font = get_cached_font(str(font_bold_path.resolve()), int(round(34.0 * scale)))
    time_label_font = get_cached_font(str(font_bold_path.resolve()), int(round(28.0 * scale)))
    time_val_font = get_cached_font(str(font_reg_path.resolve()), int(round(32.0 * scale)))

    # Nudged both text boxes over to the right by 15px
    nudge_15px = 15.0 * scale
    left_col_right_x = (855.0 * scale) + nudge_15px
    right_col_left_x = (871.6 * scale) + nudge_15px
    cur_y = 50.0 * scale

    title_str = "HRFC CHANGING ROOMS"
    d.text((right_col_left_x, cur_y), title_str, font=title_font, fill=text_info_color)
    bb_title = d.textbbox((0, 0), title_str, font=title_font)
    cur_y += (bb_title[3] - bb_title[1]) + int(round(32 * scale))

    assignments = sorted([
        (home_room_num, home_team.upper()),
        (away_room_num, opponent.upper())
    ], key=lambda x: x[0])

    for room_num, team_name in assignments:
        num_str = str(room_num)
        bb_num = d.textbbox((0, 0), num_str, font=room_num_font)
        num_w = bb_num[2] - bb_num[0]
        num_h = bb_num[3] - bb_num[1]

        bb_name = d.textbbox((0, 0), team_name, font=room_text_font)
        name_h = bb_name[3] - bb_name[1]

        row_h = max(num_h, name_h)
        d.text((left_col_right_x - num_w, cur_y + (row_h - num_h) / 2), num_str, font=room_num_font, fill=text_info_color)
        d.text((right_col_left_x, cur_y + (row_h - name_h) / 2), team_name, font=room_text_font, fill=text_cr_color)
        
        cur_y += row_h + int(round(12 * scale))

    cur_y += int(round(20 * scale))

    in_lbl = "IN"
    bb_in_lbl = d.textbbox((0, 0), in_lbl, font=time_label_font)
    in_lbl_w = bb_in_lbl[2] - bb_in_lbl[0]
    in_lbl_h = bb_in_lbl[3] - bb_in_lbl[1]

    in_str = in_time.strip()
    bb_in_val = d.textbbox((0, 0), in_str, font=time_val_font)
    in_val_h = bb_in_val[3] - bb_in_val[1]

    row_in_h = max(in_lbl_h, in_val_h)
    d.text((left_col_right_x - in_lbl_w, cur_y + (row_in_h - in_lbl_h) / 2), in_lbl, font=time_label_font, fill=text_info_color)
    d.text((right_col_left_x, cur_y + (row_in_h - in_val_h) / 2), in_str, font=time_val_font, fill=text_cr_color)
    cur_y += row_in_h + int(round(12 * scale))

    out_lbl = "OUT"
    bb_out_lbl = d.textbbox((0, 0), out_lbl, font=time_label_font)
    out_lbl_w = bb_out_lbl[2] - bb_out_lbl[0]
    out_lbl_h = bb_out_lbl[3] - bb_out_lbl[1]

    out_str = out_time.strip()
    bb_out_val = d.textbbox((0, 0), out_str, font=time_val_font)
    out_val_h = bb_out_val[3] - bb_out_val[1]

    row_out_h = max(out_lbl_h, out_val_h)
    d.text((left_col_right_x - out_lbl_w, cur_y + (row_out_h - out_lbl_h) / 2), out_lbl, font=time_label_font, fill=text_info_color)
    d.text((right_col_left_x, cur_y + (row_out_h - out_val_h) / 2), out_str, font=time_val_font, fill=text_cr_color)

    base_img.alpha_composite(txt_layer)

    # 1. Render Home Club Crest (HUNGERFORD_CREST) on Home Room Box
    home_box = CHANGING_ROOM_BOXES.get(home_room_num)
    if home_box:
        crest_w = int(round(home_box["w"] * scale))
        crest_h = int(round(home_box["h"] * scale))
        club_crest = load_club_crest(home_team, crest_w, crest_h)
        if club_crest:
            cx = (home_box["x"] + (home_box["w"] / 2.0)) * scale
            cy = (home_box["y"] + (home_box["h"] / 2.0)) * scale
            dest_x = int(round(cx - (club_crest.width / 2.0)))
            dest_y = int(round(cy - (club_crest.height / 2.0)))
            base_img.alpha_composite(club_crest, dest=(dest_x, dest_y))

    # 2. Render Away Opponent Crest on Away Room Box
    away_box = CHANGING_ROOM_BOXES.get(away_room_num)
    if away_box:
        crest_w = int(round(away_box["w"] * scale))
        crest_h = int(round(away_box["h"] * scale))
        lookup = away_crest_stem if away_crest_stem else opponent
        opp_crest = load_opponent_crest(lookup, crest_w, crest_h)
        if opp_crest:
            cx = (away_box["x"] + (away_box["w"] / 2.0)) * scale
            cy = (away_box["y"] + (away_box["h"] / 2.0)) * scale
            dest_x = int(round(cx - (opp_crest.width / 2.0)))
            dest_y = int(round(cy - (opp_crest.height / 2.0)))
            base_img.alpha_composite(opp_crest, dest=(dest_x, dest_y))

    output_filepath = OUTPUT_DIR / output_filename
    base_img.convert("RGB").save(output_filepath, "PNG")
    return output_filepath