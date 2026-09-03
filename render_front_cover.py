from pathlib import Path
from functools import lru_cache
from datetime import datetime
import re
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.xlsx"
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
COVERS_DIR = ASSETS_DIR / "covers"
OPPOSITIONS_DIR = ASSETS_DIR / "oppositions"
COMP_LOGOS_DIR = ASSETS_DIR / "comp_logos"
OUTPUT_DIR = BASE_DIR / "output"

# Base Canva Coordinate Space
CANVA_DESIGN_WIDTH = 1920.0

# Canva Bounding Boxes
OPP_BOX_X = 7.0
OPP_BOX_Y = 313.9
OPP_BOX_W = 230.3
OPP_BOX_H = 245.0

TITLE_BOX_X = 256.8
TITLE_BOX_Y = 158.1

META_BOX_X = 162.5
META_BOX_Y = 639.3

COMP_BOX_X = 256.8
COMP_BOX_Y = 449.1
COMP_BOX_W = 144.7
COMP_BOX_H = 144.7


def hex_to_rgba(hex_code: str, alpha: int = 255) -> tuple[int, int, int, int]:
    clean_hex = str(hex_code).lstrip("#").strip()
    if len(clean_hex) == 3:
        clean_hex = "".join([c * 2 for c in clean_hex])
    if len(clean_hex) != 6:
        return (255, 255, 255, alpha)
    r = int(clean_hex[0:2], 16)
    g = int(clean_hex[2:4], 16)
    b = int(clean_hex[4:6], 16)
    return (r, g, b, alpha)


@lru_cache(maxsize=4)
def get_cached_config_sheet(config_excel_path_str: str, sheet_name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(config_excel_path_str, sheet_name=sheet_name)
    except Exception:
        return pd.DataFrame()


def get_team_prefix(home_team: str) -> str:
    clean = str(home_team).strip().upper()
    if "WARRIOR" in clean:
        return "WARRIORS"
    elif "HURRICANE" in clean:
        return "HURRICANES"
    return "HRFC"


def get_team_colors(home_team: str) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    prefix = get_team_prefix(home_team)

    fallback_primary = "#FFFFFF"
    fallback_accent = "#F1B434" if prefix == "WARRIORS" else "#FFE602"

    primary_rgba = hex_to_rgba(fallback_primary)
    accent_rgba = hex_to_rgba(fallback_accent)

    if CONFIG_PATH.exists():
        teams_df = get_cached_config_sheet(str(CONFIG_PATH.resolve()), "teams")
        if not teams_df.empty and "team_prefix" in teams_df.columns:
            matched = teams_df[teams_df["team_prefix"].astype(str).str.strip().str.upper() == prefix]
            if not matched.empty:
                row = matched.iloc[0]
                for col in ["text_color_hex", "primary_color", "white_color", "text_color", "lead_color"]:
                    if col in row and pd.notna(row[col]):
                        primary_rgba = hex_to_rgba(str(row[col]).strip())
                        break

                for col in ["accent_color_hex", "accent_color", "secondary_color", "accent"]:
                    if col in row and pd.notna(row[col]):
                        accent_rgba = hex_to_rgba(str(row[col]).strip())
                        break

    return primary_rgba, accent_rgba


def get_font_specifications() -> dict:
    specs = {
        "bold_file": "Poppins-Bold.ttf",
        "regular_file": "Poppins-Regular.ttf",
        "title_pt": 71.1,
        "v_pt": 26.1,
        "subtitle_pt": 66.0,
        "date_pt": 57.0,
        "meta_pt": 46.0,
        "para_spacer_pt": 24.0,
    }

    if CONFIG_PATH.exists():
        fonts_df = get_cached_config_sheet(str(CONFIG_PATH.resolve()), "fonts")
        if fonts_df.empty:
            fonts_df = get_cached_config_sheet(str(CONFIG_PATH.resolve()), "typography")

        if not fonts_df.empty:
            if "key" in fonts_df.columns and "value" in fonts_df.columns:
                kv = dict(zip(fonts_df["key"].astype(str).str.strip().str.lower(), fonts_df["value"]))
                for k, v in kv.items():
                    if k in specs and pd.notna(v):
                        try:
                            specs[k] = float(v) if isinstance(specs[k], float) else str(v).strip()
                        except ValueError:
                            pass
            else:
                row = fonts_df.iloc[0]
                for k in specs.keys():
                    if k in row and pd.notna(row[k]):
                        try:
                            specs[k] = float(row[k]) if isinstance(specs[k], float) else str(row[k]).strip()
                        except ValueError:
                            pass

    return specs


@lru_cache(maxsize=8)
def get_cached_base_image(image_path_str: str) -> Image.Image:
    return Image.open(image_path_str).convert("RGBA")


@lru_cache(maxsize=64)
def get_cached_font(font_path_str: str, size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path_str, size=size_px)


def resolve_font_path(filename: str) -> Path:
    target = FONTS_DIR / filename
    if target.exists():
        return target

    fallbacks = [
        FONTS_DIR / "Poppins-Bold.ttf",
        FONTS_DIR / "Aptos-Bold.ttf",
        FONTS_DIR / "Poppins-Regular.ttf",
        FONTS_DIR / "Aptos.ttf",
    ]
    for fb in fallbacks:
        if fb.exists():
            return fb

    any_fonts = list(FONTS_DIR.glob("*.ttf")) + list(FONTS_DIR.glob("*.otf"))
    return any_fonts[0] if any_fonts else Path()


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


def get_cover_base_path(home_team: str) -> Path:
    clean = str(home_team).strip().upper()
    if "WARRIOR" in clean:
        stem = "COVER_WARRIORS"
    elif "HURRICANE" in clean:
        stem = "COVER_HURRICANES"
    else:
        stem = "COVER_DEFAULT"

    for ext in [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG"]:
        candidate = COVERS_DIR / f"{stem}{ext}"
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"Cover background template not found for stem: {stem} in {COVERS_DIR}")


def parse_cover_date_parts(date_str: str | None) -> tuple[str, str]:
    if not date_str:
        return "", ""
    clean = date_str.strip()
    dt = None
    for fmt in ["%d.%m.%y", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(clean, fmt)
            break
        except ValueError:
            pass

    if dt:
        day_month = dt.strftime("%d %b ").upper()
        year = dt.strftime("%Y")
        return day_month, year

    parts = clean.upper().split()
    if len(parts) >= 2:
        return " ".join(parts[:-1]) + " ", parts[-1]
    return clean.upper(), ""


def get_pack_subtitle_parts(
    home_team: str,
    lead_color: tuple[int, int, int, int],
    accent_color: tuple[int, int, int, int],
    font: ImageFont.FreeTypeFont,
) -> list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]]:
    clean = str(home_team).strip().upper()
    match = re.search(r"\bU\d+\b", clean)

    prefix = ""
    if match:
        prefix = match.group(0)
    elif "COLTS" in clean:
        prefix = "COLTS"

    if prefix:
        return [
            (f"{prefix} ", font, lead_color),
            ("WELCOME PACK", font, accent_color),
        ]
    else:
        return [
            ("WELCOME ", font, lead_color),
            ("PACK", font, accent_color),
        ]


def render_multipart_line(
    draw: ImageDraw.ImageDraw,
    parts: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]],
    start_x: int,
    start_y: int,
) -> None:
    cur_x = start_x
    for text, font, color in parts:
        if not text:
            continue
        draw.text((cur_x, start_y), text, font=font, fill=color)
        bbox = draw.textbbox((0, 0), text, font=font)
        cur_x += bbox[2] - bbox[0]


def get_line_height(font: ImageFont.FreeTypeFont) -> int:
    ascent, descent = font.getmetrics()
    return ascent + descent


def generate_front_cover(
    home_team: str,
    opponent: str,
    ko_time: str,
    match_date: str | None = None,
    referee: str | None = None,
    opponent_crest_stem: str | None = None,
    competition: str | None = None,
    output_filename: str = "output_front_cover.png",
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base_image_path = get_cover_base_path(home_team)
    base_img = get_cached_base_image(str(base_image_path.resolve())).copy()
    scale = base_img.width / CANVA_DESIGN_WIDTH

    font_specs = get_font_specifications()
    lead_color, accent_color = get_team_colors(home_team)

    path_bold = resolve_font_path(str(font_specs["bold_file"]))
    path_reg = resolve_font_path(str(font_specs["regular_file"]))

    # 1. Opposition Crest
    opp_w = int(round(OPP_BOX_W * scale))
    opp_h = int(round(OPP_BOX_H * scale))
    lookup_name = opponent_crest_stem if opponent_crest_stem else opponent
    crest_img = load_opponent_crest(lookup_name, opp_w, opp_h)

    if crest_img:
        cx = (OPP_BOX_X + (OPP_BOX_W / 2.0)) * scale
        cy = (OPP_BOX_Y + (OPP_BOX_H / 2.0)) * scale
        dest_x = int(round(cx - (crest_img.width / 2.0)))
        dest_y = int(round(cy - (crest_img.height / 2.0)))
        base_img.alpha_composite(crest_img, dest=(dest_x, dest_y))

    # 2. Competition Logo
    if competition:
        comp_w = int(round(COMP_BOX_W * scale))
        comp_h = int(round(COMP_BOX_H * scale))
        comp_img = load_competition_logo(competition, comp_w, comp_h)
        if comp_img:
            cx = (COMP_BOX_X + (COMP_BOX_W / 2.0)) * scale
            cy = (COMP_BOX_Y + (COMP_BOX_H / 2.0)) * scale
            dest_x = int(round(cx - (comp_img.width / 2.0)))
            dest_y = int(round(cy - (comp_img.height / 2.0)))
            base_img.alpha_composite(comp_img, dest=(dest_x, dest_y))

    # 3. Dynamic Text Layer
    txt_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_layer)

    # --- Title Block Typography ---
    font_team = get_cached_font(str(path_bold.resolve()), int(round(font_specs["title_pt"] * scale)))
    font_v = get_cached_font(str(path_bold.resolve()), int(round(font_specs["v_pt"] * scale)))

    t_box_x = int(round(TITLE_BOX_X * scale))
    cur_y = int(round(TITLE_BOX_Y * scale))

    # Line 1: Home Team
    prefix = get_team_prefix(home_team)
    if prefix == "WARRIORS":
        line1_parts = [
            ("BERKSHIRE ", font_team, lead_color),
            ("WARRIORS", font_team, accent_color),
        ]
    elif prefix == "HURRICANES":
        line1_parts = [
            ("HUNGERFORD ", font_team, lead_color),
            ("HURRICANES", font_team, accent_color),
        ]
    else:
        line1_parts = [
            ("HUNGERFORD ", font_team, lead_color),
            ("RFC", font_team, accent_color),
        ]
    render_multipart_line(draw, line1_parts, t_box_x, cur_y)
    cur_y += get_line_height(font_team)

    # Line 2: V
    draw.text((t_box_x, cur_y), "V", font=font_v, fill=accent_color)
    cur_y += get_line_height(font_v)

    # Line 3: Opponent
    raw_opp = str(opponent).strip().upper()
    opp_match = re.search(r"^(.*?)(?:\s+(RFC|RUFC|WRFC))?$", raw_opp)
    if opp_match:
        club_base = opp_match.group(1).strip()
        club_suffix = opp_match.group(2)
        if club_suffix:
            line3_parts = [
                (f"{club_base} ", font_team, lead_color),
                (club_suffix, font_team, accent_color),
            ]
        else:
            line3_parts = [(club_base, font_team, lead_color)]
    else:
        line3_parts = [(raw_opp, font_team, lead_color)]
    render_multipart_line(draw, line3_parts, t_box_x, cur_y)

    # --- Subtitle & Match Details Block ---
    font_sub = get_cached_font(str(path_bold.resolve()), int(round(font_specs["subtitle_pt"] * scale)))
    font_date = get_cached_font(str(path_bold.resolve()), int(round(font_specs["date_pt"] * scale)))
    font_meta = get_cached_font(str(path_reg.resolve()), int(round(font_specs["meta_pt"] * scale)))

    m_box_x = int(round(META_BOX_X * scale))
    cur_my = int(round(META_BOX_Y * scale))

    # Line 1: Subtitle (Prefix in Lead, WELCOME PACK in Accent OR WELCOME in Lead, PACK in Accent)
    sub_parts = get_pack_subtitle_parts(home_team, lead_color, accent_color, font_sub)
    render_multipart_line(draw, sub_parts, m_box_x, cur_my)
    cur_my += int(round(font_specs["subtitle_pt"] * scale))

    # Line 2: DD MMM (Lead) + YYYY (Accent)
    day_month, year_str = parse_cover_date_parts(match_date)
    if day_month or year_str:
        date_parts = [
            (day_month, font_date, lead_color),
            (year_str, font_date, accent_color),
        ]
        render_multipart_line(draw, date_parts, m_box_x, cur_my)
        cur_my += int(round(font_specs["date_pt"] * scale))

    # Paragraph gap between Date and KO/Ref
    cur_my += int(round(font_specs["para_spacer_pt"] * scale))

    # Line 3: ko (Lead) + Time (Accent)
    clean_ko = str(ko_time).strip()
    ko_parts = [
        ("ko ", font_meta, lead_color),
        (clean_ko, font_meta, accent_color),
    ]
    render_multipart_line(draw, ko_parts, m_box_x, cur_my)
    cur_my += int(round(font_specs["meta_pt"] * scale))

    # Line 4: Referee (Lead) + Official Name (Accent)
    ref_name = referee.strip() if referee and referee.strip() else "TBC"
    ref_parts = [
        ("Referee ", font_meta, lead_color),
        (ref_name, font_meta, accent_color),
    ]
    render_multipart_line(draw, ref_parts, m_box_x, cur_my)

    base_img.alpha_composite(txt_layer)

    output_filepath = OUTPUT_DIR / output_filename
    base_img.convert("RGB").save(output_filepath, "PNG")

    return output_filepath


if __name__ == "__main__":
    generate_front_cover(
        home_team="WARRIORS U16",
        opponent="ELLINGHAM & RINGWOOD RFC",
        ko_time="10:00",
        match_date="06 SEP 2026",
        referee="TBC",
        opponent_crest_stem="ELLINGHAM & RINGWOOD",
        competition="HOB",
        output_filename="test_cover_warriors.png",
    )