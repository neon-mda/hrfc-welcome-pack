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
MAX_TITLE_WIDTH = 1150.0

META_BOX_X = 162.5
META_BOX_Y = 639.3

COMP_BOX_X = 256.8
COMP_BOX_Y = 449.1
COMP_BOX_W = 144.7
COMP_BOX_H = 144.7

GOLD_ACCENT = (241, 180, 52, 255)


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
def get_cached_teams_df(config_excel_path_str: str) -> pd.DataFrame:
    try:
        return pd.read_excel(config_excel_path_str, sheet_name="teams")
    except Exception:
        return pd.DataFrame()


def get_warrior_white() -> tuple[int, int, int, int]:
    if CONFIG_PATH.exists():
        teams_df = get_cached_teams_df(str(CONFIG_PATH.resolve()))
        if not teams_df.empty and "team_prefix" in teams_df.columns:
            matched = teams_df[teams_df["team_prefix"].astype(str).str.strip().str.upper() == "WARRIORS"]
            if not matched.empty:
                row = matched.iloc[0]
                for col in ["text_color_hex", "primary_color", "white_color", "text_color"]:
                    if col in row and pd.notna(row[col]):
                        return hex_to_rgba(str(row[col]).strip())
    return (255, 255, 255, 255)


@lru_cache(maxsize=8)
def get_cached_base_image(image_path_str: str) -> Image.Image:
    return Image.open(image_path_str).convert("RGBA")


@lru_cache(maxsize=64)
def get_cached_font(font_path_str: str, size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path_str, size=size_px)


def resolve_font_path(bold: bool = True) -> Path:
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

    generic_fallbacks = list(FONTS_DIR.glob("*.ttf")) + list(FONTS_DIR.glob("*.otf"))
    return generic_fallbacks[0] if generic_fallbacks else Path()


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


def parse_pack_parts(home_team: str) -> tuple[str, str]:
    clean = str(home_team).strip().upper()
    match = re.search(r"\bU\d+\b", clean)
    if match:
        return f"{match.group(0)} ", "WELCOME PACK"
    if "COLTS" in clean:
        return "COLTS ", "WELCOME PACK"
    return "", "WELCOME PACK"


def measure_multipart_line(
    parts: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]],
    draw: ImageDraw.ImageDraw,
) -> tuple[int, int]:
    total_w = 0
    max_h = 0
    for text, font, _ in parts:
        if not text:
            continue
        bbox = draw.textbbox((0, 0), text, font=font)
        total_w += bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if h > max_h:
            max_h = h
    return total_w, max_h


def render_multipart_line(
    draw: ImageDraw.ImageDraw,
    parts: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]],
    start_x: int,
    start_y: int,
) -> int:
    cur_x = start_x
    max_h = 0
    for text, font, color in parts:
        if not text:
            continue
        draw.text((cur_x, start_y), text, font=font, fill=color)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        cur_x += w
        if h > max_h:
            max_h = h
    return max_h


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

    path_bold = resolve_font_path(bold=True)
    path_reg = resolve_font_path(bold=False)

    warrior_white = get_warrior_white()

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

    # --- Title Block Configuration ---
    base_title_fs = int(round(71.1 * scale))
    v_fs = int(round(26.1 * scale))
    font_v = get_cached_font(str(path_bold.resolve()), v_fs) if path_bold.exists() else ImageFont.load_default()

    # Determine Opponent Line Parts
    raw_opp = str(opponent).strip().upper()
    opp_match = re.search(r"^(.*?)(?:\s+(RFC|RUFC|WRFC))?$", raw_opp)
    if opp_match:
        club_base = opp_match.group(1).strip()
        club_suffix = opp_match.group(2)
    else:
        club_base = raw_opp
        club_suffix = None

    # Auto-fit title font if club name is very long
    max_w_px = MAX_TITLE_WIDTH * scale
    current_title_fs = base_title_fs
    font_title = get_cached_font(str(path_bold.resolve()), current_title_fs) if path_bold.exists() else ImageFont.load_default()

    dummy_parts = [(f"{club_base} ", font_title, warrior_white)]
    if club_suffix:
        dummy_parts.append((club_suffix, font_title, GOLD_ACCENT))
    opp_w_meas, _ = measure_multipart_line(dummy_parts, draw)

    while opp_w_meas > max_w_px and current_title_fs > int(round(46.0 * scale)):
        current_title_fs -= 2
        font_title = get_cached_font(str(path_bold.resolve()), current_title_fs)
        dummy_parts = [(f"{club_base} ", font_title, warrior_white)]
        if club_suffix:
            dummy_parts.append((club_suffix, font_title, GOLD_ACCENT))
        opp_w_meas, _ = measure_multipart_line(dummy_parts, draw)

    t_box_x = int(round(TITLE_BOX_X * scale))
    line1_y = int(round(TITLE_BOX_Y * scale))

    # Line 1 Parts
    clean_home = str(home_team).strip().upper()
    if "WARRIOR" in clean_home:
        line1_parts = [
            ("BERKSHIRE ", font_title, warrior_white),
            ("WARRIORS", font_title, GOLD_ACCENT),
        ]
    elif "HURRICANE" in clean_home:
        line1_parts = [
            ("HUNGERFORD ", font_title, warrior_white),
            ("HURRICANES", font_title, GOLD_ACCENT),
        ]
    else:
        line1_parts = [
            ("HUNGERFORD ", font_title, warrior_white),
            ("RFC", font_title, GOLD_ACCENT),
        ]

    # Line 3 Parts
    if club_suffix:
        line3_parts = [
            (f"{club_base} ", font_title, warrior_white),
            (club_suffix, font_title, GOLD_ACCENT),
        ]
    else:
        line3_parts = [(club_base, font_title, warrior_white)]

    # Draw Line 1
    render_multipart_line(draw, line1_parts, t_box_x, line1_y)

    # Compute bounding ink bottoms and tops for strict equidistance
    # Dummy draw to get exact bounding box of Line 1
    _, line1_h = measure_multipart_line(line1_parts, draw)
    line1_bottom = line1_y + line1_h

    # v glyph vertical ink bounds relative to render point
    v_bbox = draw.textbbox((0, 0), "v", font=font_v)
    v_top_offset = v_bbox[1]
    v_height = v_bbox[3] - v_bbox[1]

    # Desired clear gap above and below v
    equidistant_gap = int(round(16.0 * scale))

    # Position v so its top ink edge is exactly equidistant_gap below line 1 bottom
    v_render_y = line1_bottom + equidistant_gap - v_top_offset
    draw.text((t_box_x, v_render_y), "v", font=font_v, fill=GOLD_ACCENT)

    # Position Line 3 so its top ink edge is exactly equidistant_gap below v bottom ink edge
    v_bottom = (v_render_y + v_top_offset) + v_height
    line3_y = v_bottom + equidistant_gap

    # Draw Line 3
    render_multipart_line(draw, line3_parts, t_box_x, line3_y)

    # --- Subtitle & Match Details Block ---
    fs_sub = int(round(66.0 * scale))
    fs_date = int(round(57.0 * scale))
    fs_meta = int(round(46.0 * scale))

    font_sub = get_cached_font(str(path_bold.resolve()), fs_sub) if path_bold.exists() else ImageFont.load_default()
    font_date = get_cached_font(str(path_bold.resolve()), fs_date) if path_bold.exists() else ImageFont.load_default()
    font_meta = get_cached_font(str(path_reg.resolve()), fs_meta) if path_reg.exists() else ImageFont.load_default()

    m_box_x = int(round(META_BOX_X * scale))
    cur_my = int(round(META_BOX_Y * scale))
    meta_line_gap = int(round(10.0 * scale))

    # Line 1: UXX (White) + WELCOME PACK (Gold)
    age_prefix, pack_suffix = parse_pack_parts(home_team)
    sub_parts = []
    if age_prefix:
        sub_parts.append((age_prefix, font_sub, warrior_white))
    sub_parts.append((pack_suffix, font_sub, GOLD_ACCENT))
    s_h = render_multipart_line(draw, sub_parts, m_box_x, cur_my)
    cur_my += s_h + meta_line_gap

    # Line 2: DD MMM (White) + YYYY (Gold)
    day_month, year_str = parse_cover_date_parts(match_date)
    if day_month or year_str:
        date_parts = [
            (day_month, font_date, warrior_white),
            (year_str, font_date, GOLD_ACCENT),
        ]
        d_h = render_multipart_line(draw, date_parts, m_box_x, cur_my)
        cur_my += d_h + meta_line_gap

    # Distinct gap separating the pack title/date block from ko/referee
    date_ko_spacer = int(round(30.0 * scale))
    cur_my += date_ko_spacer

    # Line 3: ko (White) + Time (Gold)
    clean_ko = str(ko_time).strip()
    ko_parts = [
        ("ko ", font_meta, warrior_white),
        (clean_ko, font_meta, GOLD_ACCENT),
    ]
    k_h = render_multipart_line(draw, ko_parts, m_box_x, cur_my)
    cur_my += k_h + meta_line_gap

    # Line 4: Referee (White) + Official Name (Gold)
    ref_name = referee.strip() if referee and referee.strip() else "TBC"
    ref_parts = [
        ("Referee ", font_meta, warrior_white),
        (ref_name, font_meta, GOLD_ACCENT),
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
        match_date="06.09.26",
        referee="TBC",
        opponent_crest_stem="ELLINGHAM & RINGWOOD",
        competition="HOB",
        output_filename="test_cover_warriors.png",
    )