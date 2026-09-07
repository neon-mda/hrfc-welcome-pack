from pathlib import Path
from functools import lru_cache
from datetime import datetime, timedelta
import math
import re
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MAPS_DIR = ASSETS_DIR / "maps"
COVERS_DIR = ASSETS_DIR / "covers"
OUTPUT_DIR = BASE_DIR / "output"

CANVA_DESIGN_WIDTH = 1920.0

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

def resolve_eventlogs_template_path(home_team: str) -> Path:
    clean = str(home_team).strip().upper()
    prefix = "DEFAULT"
    if "WARRIOR" in clean:
        prefix = "WARRIORS"
    elif "HURRICANE" in clean:
        prefix = "HURRICANES"

    candidates = [
        COVERS_DIR / f"EVENTLOGS_{prefix}.png",
        COVERS_DIR / "EVENTLOGS_DEFAULT.png",
        COVERS_DIR / "EVENTLOGS.png",
        MAPS_DIR / f"EVENTLOGS_{prefix}.png",
        MAPS_DIR / "EVENTLOGS.png",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Event logs template not found for prefix '{prefix}' in covers or maps directory.")

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

def get_team_colors(config_excel_path: Path, home_team: str):
    clean = str(home_team).strip().upper()
    if "WARRIOR" in clean:
        default_info = (172, 7, 83, 255)
        default_fg = (248, 249, 255, 255)
        default_bg = (172, 7, 83, 255)
    else:
        default_info = (130, 28, 52, 255)
        default_fg = (255, 230, 2, 255)
        default_bg = (130, 28, 52, 255)
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
                    fg_col = next((c for c in df.columns if str(c).strip().lower() in ['text_fg', 'fg', 'foreground']), None)
                    bg_col = next((c for c in df.columns if str(c).strip().lower() in ['text_bg', 'bg']), None)

                    if info_col and pd.notna(row[info_col]):
                        default_info = parse_color(row[info_col], default_info)
                    if cr_col and pd.notna(row[cr_col]):
                        default_cr = parse_color(row[cr_col], default_cr)
                    if fg_col and pd.notna(row[fg_col]):
                        default_fg = parse_color(row[fg_col], default_fg)
                    if bg_col and pd.notna(row[bg_col]):
                        default_bg = parse_color(row[bg_col], default_bg)
    except Exception:
        pass

    return default_info, default_cr, default_fg, default_bg

def generate_eventlogs_page(
    config_excel_path: Path,
    home_team: str,
    ko_time: str = "13:00",
    match_length_mins: int = 70,
    output_filename: str = "output_eventlogs.png",
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    template_path = resolve_eventlogs_template_path(home_team)

    text_info_color, text_cr_color, text_fg_color, text_bg_color = get_team_colors(config_excel_path, home_team)

    base_img = get_cached_base_image(str(template_path.resolve())).copy()
    scale = base_img.width / CANVA_DESIGN_WIDTH

    txt_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(txt_layer)

    font_bold_path = resolve_font_path("Bold")
    font_reg_path = resolve_font_path("Regular")

    header_font = get_cached_font(str(font_bold_path.resolve()), int(round(26.0 * scale)))
    regular_font = get_cached_font(str(font_reg_path.resolve()), int(round(26.0 * scale)))
    bold_font = get_cached_font(str(font_bold_path.resolve()), int(round(26.0 * scale)))

    try:
        ko_dt = datetime.strptime(ko_time.strip(), "%H:%M")
    except Exception:
        ko_dt = datetime.strptime("13:00", "%H:%M")

    t_arrive = (ko_dt - timedelta(minutes=75)).strftime("%H:%M")
    t_warmup = (ko_dt - timedelta(minutes=60)).strftime("%H:%M")
    t_ko = ko_dt.strftime("%H:%M")
    t_final = (ko_dt + timedelta(minutes=match_length_mins + 20)).strftime("%H:%M")
    
    out_dt = ko_dt + timedelta(minutes=match_length_mins + 20 + 20)
    t_out = out_dt.strftime("%H:%M")
    t_meal = (out_dt + timedelta(minutes=10)).strftime("%H:%M")

    col_time_x = 1030.0 * scale
    col_activity_x = 1150.0 * scale
    col_location_x = 1590.0 * scale

    header_y = 260.0 * scale
    d.text((col_time_x, header_y), "TIME", font=header_font, fill=text_cr_color)
    d.text((col_activity_x, header_y), "ACTIVITY", font=header_font, fill=text_cr_color)
    d.text((col_location_x, header_y), "LOCATION", font=header_font, fill=text_cr_color)

    rows = [
        (t_arrive, "PLAYERS ARRIVE & CHANGE", "Changing Room", False),
        (t_warmup, "WARM-UP & REFEREE'S BRIEFING", "On-pitch", False),
        (t_ko, "KICK-OFF", "", True),
        (t_final, "FINAL WHISTLE", "latest", True),
        ("", "SHOWERS & CHANGE", "Changing room", False),
        (t_out, "TIDY & EXIT CHANGING ROOM", "", False),
        (t_meal, "POST-MATCH MEAL", "Clubhouse", False),
    ]

    start_y = 355.0 * scale
    row_height = 68.0 * scale

    max_text_right = 0
    for idx, (t_str, act_str, loc_str, is_highlighted) in enumerate(rows):
        cur_y = start_y + (idx * row_height)
        curr_font = bold_font if is_highlighted else regular_font
        act_bb = d.textbbox((col_activity_x, cur_y), act_str, font=curr_font)
        loc_bb = d.textbbox((col_location_x, cur_y), loc_str, font=curr_font) if loc_str else act_bb
        max_text_right = max(max_text_right, act_bb[2], loc_bb[2])
    
    global_right_extent = max_text_right + int(round(35 * scale))

    for idx, (t_str, act_str, loc_str, is_highlighted) in enumerate(rows):
        cur_y = start_y + (idx * row_height)
        row_font = bold_font if is_highlighted else regular_font

        if is_highlighted:
            bar_box = [
                int(round(col_time_x - 15 * scale)),
                int(round(cur_y - 6 * scale)),
                int(round(global_right_extent)),
                int(round(cur_y + 44 * scale))
            ]
            d.rectangle(bar_box, fill=text_info_color)
            text_col = text_fg_color
        else:
            text_col = text_cr_color

        if t_str == "↳":
            d.text((col_time_x, cur_y), t_str, font=bold_font, fill=text_bg_color)
        else:
            d.text((col_time_x, cur_y), t_str, font=row_font, fill=text_col)

        d.text((col_activity_x, cur_y), act_str, font=row_font, fill=text_col)
        if loc_str:
            d.text((col_location_x, cur_y), loc_str, font=row_font, fill=text_col)

    base_img.alpha_composite(txt_layer)

    output_filepath = OUTPUT_DIR / output_filename
    base_img.convert("RGB").save(output_filepath, "PNG")
    return output_filepath