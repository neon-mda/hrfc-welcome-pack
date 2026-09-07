from pathlib import Path
from functools import lru_cache
from datetime import datetime
import math
import re
import textwrap

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.xlsx"

ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MAPS_DIR = ASSETS_DIR / "maps"
OPPOSITIONS_DIR = ASSETS_DIR / "oppositions"
COMP_LOGOS_DIR = ASSETS_DIR / "comp_logos"

OUTPUT_DIR = BASE_DIR / "output"


# ============================================================
# DESIGN / LAYOUT CONSTANTS
# ============================================================

CANVA_DESIGN_WIDTH = 790.0

# Right-side graphic banner
OPPONENT_BOX_W = 170.0
OPPONENT_BOX_H = 160.0

PITCH_OPP_CX = 695.0
PITCH_OPP_CY = 975.0

COMP_LOGO_MAX_W = 160.0
COMP_LOGO_MAX_H = 160.0

PITCH_COMP_CX = 695.0
PITCH_COMP_CY = 625.0


# ============================================================
# COLOUR HELPERS
# ============================================================

def hex_to_rgba(
    hex_code: str,
    alpha: int = 255
) -> tuple[int, int, int, int]:

    clean_hex = str(hex_code).lstrip("#").strip()

    if len(clean_hex) == 3:
        clean_hex = "".join([c * 2 for c in clean_hex])

    if len(clean_hex) != 6:
        return (255, 255, 255, alpha)

    try:
        r = int(clean_hex[0:2], 16)
        g = int(clean_hex[2:4], 16)
        b = int(clean_hex[4:6], 16)
    except ValueError:
        return (255, 255, 255, alpha)

    return (r, g, b, alpha)


# ============================================================
# TEAM HELPERS
# ============================================================

def get_team_prefix(home_team: str) -> str:
    clean = str(home_team).strip().upper()

    if "WARRIOR" in clean:
        return "WARRIORS"

    if "HURRICANE" in clean:
        return "HURRICANES"

    return "DEFAULT"


@lru_cache(maxsize=4)
def get_cached_config_dfs(
    config_excel_path: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:

    path_obj = Path(config_excel_path).resolve()

    if not path_obj.exists():
        raise FileNotFoundError(
            f"Config file not found at: {path_obj}"
        )

    xls = pd.ExcelFile(
        path_obj,
        engine="openpyxl"
    )

    sheet_lookup = {
        str(s).strip().lower(): s
        for s in xls.sheet_names
    }

    anchors_sheet = sheet_lookup.get("pitch_anchors")

    if not anchors_sheet:
        raise ValueError(
            f"Sheet 'pitch_anchors' not found in {path_obj.name}"
        )

    anchors_df = pd.read_excel(
        xls,
        sheet_name=anchors_sheet
    )

    anchors_df.columns = [
        str(c).strip()
        for c in anchors_df.columns
    ]

    teams_sheet = sheet_lookup.get("teams")

    if teams_sheet:
        teams_df = pd.read_excel(
            xls,
            sheet_name=teams_sheet
        )

        teams_df.columns = [
            str(c).strip()
            for c in teams_df.columns
        ]
    else:
        teams_df = pd.DataFrame()

    return anchors_df, teams_df


def get_team_palette(
    home_team: str,
    teams_df: pd.DataFrame
) -> dict:

    prefix = get_team_prefix(home_team)

    palette = {
        "text_primary": (
            (248, 249, 255, 255)
            if prefix == "WARRIORS"
            else (255, 255, 255, 255)
        ),

        "text_accent": (
            (212, 175, 55, 255)
            if prefix == "WARRIORS"
            else (255, 230, 2, 255)
        ),

        "text_info": (
            (172, 7, 83, 255)
            if prefix == "WARRIORS"
            else (130, 28, 52, 255)
        ),
    }

    if (
        not teams_df.empty
        and "team_prefix" in teams_df.columns
    ):

        matched = teams_df[
            teams_df["team_prefix"]
            .astype(str)
            .str.strip()
            .str.upper()
            == prefix
        ]

        if matched.empty and prefix != "DEFAULT":
            matched = teams_df[
                teams_df["team_prefix"]
                .astype(str)
                .str.strip()
                .str.upper()
                == "DEFAULT"
            ]

        if not matched.empty:

            row = matched.iloc[0]

            if (
                "text_primary" in row
                and pd.notna(row["text_primary"])
            ):
                palette["text_primary"] = hex_to_rgba(
                    str(row["text_primary"])
                )

            if (
                "text_accent" in row
                and pd.notna(row["text_accent"])
            ):
                palette["text_accent"] = hex_to_rgba(
                    str(row["text_accent"])
                )

            if (
                "text_info" in row
                and pd.notna(row["text_info"])
            ):
                palette["text_info"] = hex_to_rgba(
                    str(row["text_info"])
                )

    return palette


# ============================================================
# IMAGE / FONT CACHING
# ============================================================

@lru_cache(maxsize=16)
def get_cached_base_image(
    image_path_str: str
) -> Image.Image:

    return Image.open(image_path_str).convert("RGBA")


@lru_cache(maxsize=64)
def get_cached_font(
    font_path_str: str,
    size_px: int
) -> ImageFont.FreeTypeFont:

    return ImageFont.truetype(
        font_path_str,
        size=size_px
    )


# ============================================================
# FONT RESOLUTION
# ============================================================

def resolve_font_path(
    style: str = "Bold"
) -> Path:

    clean_style = str(style).strip().lower()

    if "semi" in clean_style:
        filename = "Poppins-SemiBold.ttf"

    elif "regular" in clean_style:
        filename = "Poppins-Regular.ttf"

    elif "medium" in clean_style:
        filename = "Poppins-Medium.ttf"

    else:
        filename = "Poppins-Bold.ttf"

    target = FONTS_DIR / filename

    if target.exists():
        return target

    fallbacks = [
        FONTS_DIR / "Poppins-Bold.ttf",
        FONTS_DIR / "Aptos-Bold.ttf",
        FONTS_DIR / "Poppins-Regular.ttf",
        FONTS_DIR / "Aptos.ttf",
    ]

    for fallback in fallbacks:
        if fallback.exists():
            return fallback

    generic = (
        list(FONTS_DIR.glob("*.ttf"))
        + list(FONTS_DIR.glob("*.otf"))
    )

    return generic[0] if generic else Path()


# ============================================================
# MAP RESOLUTION
# ============================================================

def resolve_map_image_path(
    base_image_val: str,
    home_team: str
) -> Path:

    prefix = get_team_prefix(home_team)

    raw_filename = str(base_image_val).strip()

    adapted_filename = re.sub(
        r"^(WARRIORS|HURRICANES|DEFAULT)_",
        f"{prefix}_",
        raw_filename,
        flags=re.IGNORECASE,
    )

    candidates = [
        MAPS_DIR / adapted_filename,
        MAPS_DIR / raw_filename,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Base map image not found for candidates: "
        f"{candidates} in {MAPS_DIR}"
    )


# ============================================================
# COMPETITION LOGO
# ============================================================

@lru_cache(maxsize=32)
def load_competition_logo(
    comp_code: str | None,
    max_w_px: int,
    max_h_px: int
) -> Image.Image | None:

    if not comp_code or pd.isna(comp_code):
        return None

    clean_code = str(comp_code).strip()

    clean_code = re.sub(
        r"\.(png|jpg|jpeg)$",
        "",
        clean_code,
        flags=re.IGNORECASE,
    )

    if (
        not clean_code
        or clean_code.upper()
        in ["NONE", "FRIENDLY", "NAN"]
    ):
        return None

    stems = [
        clean_code,
        clean_code.upper(),
        clean_code.replace(" ", "_"),
        clean_code.replace(" ", ""),
    ]

    if clean_code.upper() in [
        "UGIRLSNATCUP",
        "GIRLS NATIONAL CUP",
        "NAT CUP",
        "NATIONAL CUP",
    ]:
        stems.append("U16GIRLSNATCUP")

    for stem in stems:

        for ext in [
            ".png",
            ".PNG",
            ".jpg",
            ".JPG",
            ".jpeg",
            ".JPEG",
        ]:

            candidate = COMP_LOGOS_DIR / f"{stem}{ext}"

            if candidate.exists():

                img = Image.open(
                    candidate
                ).convert("RGBA")

                img.thumbnail(
                    (max_w_px, max_h_px),
                    Image.Resampling.LANCZOS
                )

                return img

    return None


# ============================================================
# OPPONENT CREST
# ============================================================

@lru_cache(maxsize=64)
def load_opponent_crest(
    crest_stem: str,
    max_w_px: int,
    max_h_px: int
) -> Image.Image | None:

    raw_name = crest_stem.strip()

    base_name = re.sub(
        r"\b(RFC|RUFC|WRFC|U\d+|WARRIORS|HURRICANES|BOYS|GIRLS)\b",
        "",
        raw_name,
        flags=re.IGNORECASE,
    ).strip()

    search_terms = {
        raw_name,
        base_name
    }

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

            img = Image.open(
                path
            ).convert("RGBA")

            img.thumbnail(
                (max_w_px, max_h_px),
                Image.Resampling.LANCZOS
            )

            return img

    return None


# ============================================================
# NUMERIC / DATE HELPERS
# ============================================================

def parse_numeric(
    val,
    default: float = 0.0
) -> float:

    if pd.isna(val):
        return default

    if str(val).strip() in [
        "-",
        "",
        "nan",
        "None"
    ]:
        return default

    try:
        return float(val)

    except (ValueError, TypeError):
        return default


def format_header_date(
    match_date_str: str | None
) -> str:

    if not match_date_str:
        return datetime.today().strftime("%d.%m.%y")

    clean = match_date_str.strip()

    for fmt in [
        "%d %b %Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d.%m.%y",
    ]:

        try:

            dt = datetime.strptime(
                clean,
                fmt
            )

            return dt.strftime("%d.%m.%y")

        except ValueError:
            pass

    return clean


# ============================================================
# PITCH MAP GENERATOR
# ============================================================

def generate_pitch_map(
    config_excel_path: Path,
    pitch_key: str,
    home_team: str,
    opponent: str,
    ko_time: str,
    opponent_alias: str | None = None,
    opponent_crest_stem: str | None = None,
    match_date: str | None = None,
    is_provisional: bool = False,
    competition: str | None = None,
    output_filename: str = "output_pitch_map.png",
) -> Path:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # 1. LOAD CONFIGURATION
    # --------------------------------------------------------

    anchors_df, teams_df = get_cached_config_dfs(
        config_excel_path
    )

    row_match = anchors_df[
        anchors_df["pitch_key"]
        .astype(str)
        .str.strip()
        .str.upper()
        ==
        str(pitch_key)
        .strip()
        .upper()
    ]

    if row_match.empty:
        raise KeyError(
            f"Pitch key '{pitch_key}' "
            "not found in 'pitch_anchors' sheet."
        )

    anchor_row = row_match.iloc[0]


    # --------------------------------------------------------
    # 2. BASE IMAGE & SCALE CALIBRATION
    # --------------------------------------------------------

    base_image_file = anchor_row.get(
        "base_image",
        f"{pitch_key}.png"
    )

    base_map_path = resolve_map_image_path(
        base_image_file,
        home_team
    )

    base_img = get_cached_base_image(
        str(base_map_path.resolve())
    ).copy()

    scale = (
        base_img.width
        / CANVA_DESIGN_WIDTH
    )

    palette = get_team_palette(
        home_team,
        teams_df
    )


    # --------------------------------------------------------
    # 3. TOP-RIGHT HEADER (Right-aligned to rightmost edge of logo stack at x = 780.0)
    # --------------------------------------------------------

    txt_layer = Image.new(
        "RGBA",
        base_img.size,
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(
        txt_layer
    )

    font_bold_path = resolve_font_path(
        "Bold"
    )

    font_reg_path = resolve_font_path(
        "Regular"
    )

    hdr_team_font = get_cached_font(
        str(font_bold_path.resolve()),
        int(round(42.0 * scale))
    )

    hdr_sub_font = get_cached_font(
        str(font_reg_path.resolve()),
        int(round(30.0 * scale))
    )

    hdr_prov_font = get_cached_font(
        str(font_bold_path.resolve()),
        int(round(14.0 * scale))
    )

    hdr_date_font = get_cached_font(
        str(font_bold_path.resolve()),
        int(round(32.0 * scale))
    )

    hdr_right_margin = int(
        round(780.0 * scale)
    )

    hdr_y = int(
        round(12.0 * scale)
    )


    # Home team (Prefix with HRFC if not Warriors or Hurricanes)
    raw_home = str(home_team).strip().upper()
    if "WARRIOR" in raw_home or "HURRICANE" in raw_home:
        line1 = raw_home
    else:
        line1 = f"HRFC {raw_home}" if not raw_home.startswith("HRFC") else raw_home

    bb1 = draw.textbbox(
        (0, 0),
        line1,
        font=hdr_team_font
    )

    draw.text(
        (
            hdr_right_margin
            - (bb1[2] - bb1[0]),
            hdr_y
        ),
        line1,
        font=hdr_team_font,
        fill=palette["text_primary"]
    )

    hdr_y += (
        bb1[3] - bb1[1]
    ) + int(round(6 * scale))


    # HRFC PITCHES

    line2 = "HUNGERFORD RFC"

    bb2 = draw.textbbox(
        (0, 0),
        line2,
        font=hdr_sub_font
    )

    draw.text(
        (
            hdr_right_margin
            - (bb2[2] - bb2[0]),
            hdr_y
        ),
        line2,
        font=hdr_sub_font,
        fill=palette["text_primary"]
    )

    hdr_y += (
        bb2[3] - bb2[1]
    ) + int(round(12 * scale))  # <-- Increased gap between line 2 and provisional/date


    # Provisional

    if is_provisional:

        bb_prov = draw.textbbox(
            (0, 0),
            "PROVISIONAL",
            font=hdr_prov_font
        )

        draw.text(
            (
                hdr_right_margin
                - (bb_prov[2] - bb_prov[0]),
                hdr_y
            ),
            "PROVISIONAL",
            font=hdr_prov_font,
            fill=palette["text_accent"]
        )

        hdr_y += (
            bb_prov[3] - bb_prov[1]
        ) + int(round(2 * scale))  # <-- Gap between provisional and date


    # Date

    date_str = format_header_date(
        match_date
    )

    bb_date = draw.textbbox(
        (0, 0),
        date_str,
        font=hdr_date_font
    )

    draw.text(
        (
            hdr_right_margin
            - (bb_date[2] - bb_date[0]),
            hdr_y
        ),
        date_str,
        font=hdr_date_font,
        fill=palette["text_accent"]
    )


    # --------------------------------------------------------
    # 4. INSIDE-PITCH TEXT (Scaled Canva Mock Bounding Boxes & 28.8° Rotation)
    # --------------------------------------------------------

    clean_key = str(pitch_key).strip().upper()

    if clean_key == "P2_WHOLE":
        box_x, box_y, box_w, box_h = 442, 350, 187.6, 119.7
    elif clean_key == "P2_BOTTOM":
        box_x, box_y, box_w, box_h = 412, 400, 187.6, 119.7
    elif clean_key == "P2_TOP":
        box_x, box_y, box_w, box_h = 476, 305, 187.6, 96.7
    else:
        box_x = parse_numeric(anchor_row.get("x", 0.0))
        box_y = parse_numeric(anchor_row.get("y", 0.0))
        box_w = parse_numeric(anchor_row.get("width", 200.0))
        box_h = parse_numeric(anchor_row.get("height", 100.0))

    # Read rotation angle dynamically from config and apply the correct PIL sign
    raw_angle = anchor_row.get("text_angle", anchor_row.get("angle", 0.0))
    angle_val = parse_numeric(raw_angle, 0.0)
    
    if "P2" in clean_key and angle_val > 0:
        pil_rotation_angle = -angle_val
    else:
        pil_rotation_angle = -angle_val


    # --------------------------------------------------------
    # TEXT CONTENT & ALIAS RESOLUTION (Needed early for Pitch 5 check)
    # --------------------------------------------------------

    p5_prefixes = ("P5", "5A", "5B", "5C", "5D", "5E")
    is_pitch_5 = clean_key.startswith(p5_prefixes)

    if is_pitch_5 and opponent_alias:
        display_opp = opponent_alias.strip().upper()
    else:
        display_opp = opponent.strip().upper()

    ko_str = f"KO {ko_time.strip()}"

    max_line_w_px = max(int(round((box_w - 16) * scale)), 50)


    # --------------------------------------------------------
    # TEXT SETTINGS & READABLE LINE SPACING (90% scale for P5)
    # --------------------------------------------------------

    line_spacing_mult = parse_numeric(
        anchor_row.get(
            "line_spacing",
            1.08
        ),
        1.08
    )

    p5_size_multiplier = 0.9 if is_pitch_5 else 1.0

    l1_pt = parse_numeric(anchor_row.get("l1_size", 26.0), 26.0) * p5_size_multiplier
    l1_style = str(anchor_row.get("l1_style", "Bold"))

    l2_pt = parse_numeric(anchor_row.get("l2_size", 16.1), 16.1) * p5_size_multiplier
    l2_style = str(anchor_row.get("l2_style", "Regular"))

    l3_pt = parse_numeric(anchor_row.get("l3_size", 22.0), 22.0) * p5_size_multiplier
    l3_style = str(anchor_row.get("l3_style", "Bold"))

    l4_pt = parse_numeric(anchor_row.get("l4_size", 16.1), 16.1) * p5_size_multiplier
    l4_style = str(anchor_row.get("l4_style", "Regular"))


    # --------------------------------------------------------
    # FONTS
    # --------------------------------------------------------

    f1 = get_cached_font(str(resolve_font_path(l1_style).resolve()), int(round(l1_pt * scale)))
    f2 = get_cached_font(str(resolve_font_path(l2_style).resolve()), int(round(l2_pt * scale)))
    f3 = get_cached_font(str(resolve_font_path(l3_style).resolve()), int(round(l3_pt * scale)))
    f4 = get_cached_font(str(resolve_font_path(l4_style).resolve()), int(round(l4_pt * scale)))


    # --------------------------------------------------------
    # AUTOMATIC WORD WRAPPING
    # --------------------------------------------------------

    def wrap_text(text: str, font: ImageFont.FreeTypeFont) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines = []
        current_line = words[0]
        dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        d = ImageDraw.Draw(dummy_img)
        for word in words[1:]:
            test_line = f"{current_line} {word}"
            bb = d.textbbox((0, 0), test_line, font=font)
            if (bb[2] - bb[0]) <= max_line_w_px:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        return lines

    wrapped_home = wrap_text(line1, f1)
    wrapped_opp = wrap_text(display_opp, f3)

    # Apply conditional spacer for P2_TOP only if opposition name wraps to multiple lines
    top_spacer_offset = 0.0
    if clean_key == "P2_TOP" and len(wrapped_opp) > 1:
        top_spacer_offset = 10.0 * scale

    pitch_lines = []
    for line in wrapped_home:
        pitch_lines.append((line, f1, palette["text_primary"], l1_pt))

    if not is_pitch_5:
        pitch_lines.append(("v", f2, palette["text_primary"], l2_pt))

    for line in wrapped_opp:
        pitch_lines.append((line, f3, palette["text_primary"], l3_pt))

    pitch_lines.append((ko_str, f4, palette["text_primary"], l4_pt))


    # --------------------------------------------------------
    # MEASURE TEXT & BREATHABLE GAPS
    # --------------------------------------------------------

    dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)

    line_bboxes = []
    for idx, (txt, fnt, _, _) in enumerate(pitch_lines):
        if is_pitch_5 and idx == len(wrapped_home):
            bb_v = dummy_draw.textbbox((0, 0), "v ", font=f2)
            bb_t = dummy_draw.textbbox((0, 0), txt, font=f3)
            combined_w = (bb_v[2] - bb_v[0]) + (bb_t[2] - bb_t[0])
            combined_h = max(bb_v[3] - bb_v[1], bb_t[3] - bb_t[1])
            line_bboxes.append((0, 0, combined_w, combined_h))
        else:
            line_bboxes.append(dummy_draw.textbbox((0, 0), txt, font=fnt))

    line_widths = [bb[2] - bb[0] for bb in line_bboxes]
    line_heights = [bb[3] - bb[1] for bb in line_bboxes]

    line_gaps = [
        int(round(max(pt * 0.35, pt * (line_spacing_mult - 1.0) * 2.5) * scale))
        for _, _, _, pt in pitch_lines[:-1]
    ]

    total_txt_h = sum(line_heights) + sum(line_gaps)
    max_txt_w = max(line_widths) if line_widths else 10


    # --------------------------------------------------------
    # PIL ROTATED TEXT PIPELINE
    # --------------------------------------------------------

    pad = int(round(16 * scale))
    canvas_w = max_txt_w + (pad * 2)
    canvas_h = total_txt_h + (pad * 2)

    text_img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(text_img)

    cur_pitch_y = pad
    opp_start_line_idx = len(wrapped_home) if is_pitch_5 else -1

    for idx, (txt, fnt, col, _) in enumerate(pitch_lines):
        if is_pitch_5 and idx == opp_start_line_idx:
            v_text = "v "
            opp_text = txt
            
            ascent_v, _ = f2.getmetrics()
            ascent_opp, _ = f3.getmetrics()
            max_ascent = max(ascent_v, ascent_opp)
            
            bb_v = dummy_draw.textbbox((0, 0), v_text, font=f2)
            bb_opp = dummy_draw.textbbox((0, 0), opp_text, font=f3)
            
            v_w = bb_v[2] - bb_v[0]
            opp_w = bb_opp[2] - bb_opp[0]
            total_line_w = v_w + opp_w
            
            cur_pitch_x = int(round((canvas_w - total_line_w) / 2.0))
            
            y_v = cur_pitch_y + (max_ascent - ascent_v) - bb_v[1]
            y_opp = cur_pitch_y + (max_ascent - ascent_opp) - bb_opp[1]
            
            t_draw.text(
                (cur_pitch_x - bb_v[0], y_v),
                v_text,
                font=f2,
                fill=col
            )
            t_draw.text(
                (cur_pitch_x + v_w - bb_opp[0], y_opp),
                opp_text,
                font=f3,
                fill=col
            )
        else:
            bb = line_bboxes[idx]
            txt_w = bb[2] - bb[0]
            cur_pitch_x = int(round((canvas_w - txt_w) / 2.0))
            t_draw.text(
                (cur_pitch_x - bb[0], cur_pitch_y - bb[1]),
                txt,
                font=fnt,
                fill=col
            )

        gap = line_gaps[idx] if idx < len(line_gaps) else 0
        cur_pitch_y += line_heights[idx] + gap

    if abs(pil_rotation_angle) > 0.01:
        rotated_text_img = text_img.rotate(
            pil_rotation_angle,
            expand=True,
            resample=Image.Resampling.BICUBIC
        )
    else:
        rotated_text_img = text_img

    center_x = (box_x + (box_w / 2.0)) * scale
    if clean_key == "P2_TOP":
        center_x += (-8.0 * scale)

    center_y = (box_y + (box_h / 2.0)) * scale + top_spacer_offset

    paste_x = center_x - (rotated_text_img.width / 2.0)
    paste_y = center_y - (rotated_text_img.height / 2.0)

    txt_layer.alpha_composite(
        rotated_text_img,
        dest=(int(round(paste_x)), int(round(paste_y)))
    )
    base_img.alpha_composite(txt_layer)


    # ========================================================
    # 5. LOGOS — RIGHT-SIDE PANEL
    # ========================================================

    if competition:
        comp_img = load_competition_logo(
            competition,
            int(round(COMP_LOGO_MAX_W * scale)),
            int(round(COMP_LOGO_MAX_H * scale)),
        )

        if comp_img:
            comp_cx = PITCH_COMP_CX * scale
            comp_cy = PITCH_COMP_CY * scale

            comp_dest_x = int(round(comp_cx - (comp_img.width / 2.0)))
            comp_dest_y = int(round(comp_cy - (comp_img.height / 2.0)))

            base_img.alpha_composite(
                comp_img,
                dest=(comp_dest_x, comp_dest_y)
            )

    lookup_name = (
        opponent_crest_stem
        if opponent_crest_stem
        else opponent
    )

    crest_img = load_opponent_crest(
        lookup_name,
        int(round(OPPONENT_BOX_W * scale)),
        int(round(OPPONENT_BOX_H * scale)),
    )

    if crest_img:
        cx = PITCH_OPP_CX * scale
        cy = PITCH_OPP_CY * scale

        dest_x = int(round(cx - (crest_img.width / 2.0)))
        dest_y = int(round(cy - (crest_img.height / 2.0)))

        base_img.alpha_composite(
            crest_img,
            dest=(dest_x, dest_y)
        )


    # ========================================================
    # 6. SAVE
    # ========================================================

    output_filepath = OUTPUT_DIR / output_filename

    base_img.convert("RGB").save(
        output_filepath,
        "PNG"
    )

    return output_filepath