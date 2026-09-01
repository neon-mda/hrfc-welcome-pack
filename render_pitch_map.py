from pathlib import Path
import math
import re
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MAPS_DIR = ASSETS_DIR / "maps"
OPPOSITIONS_DIR = ASSETS_DIR / "oppositions"
OUTPUT_DIR = BASE_DIR / "output"

CANVA_DESIGN_WIDTH = 790.0

# Opposition crest bounding box and centre in Canva space
OPPONENT_BOX_W = 171.5
OPPONENT_BOX_H = 192.0
OPPONENT_CREST_CX = 610.5 + (OPPONENT_BOX_W / 2.0)  # 696.25
OPPONENT_CREST_CY = 883.5 + (OPPONENT_BOX_H / 2.0)  # 979.5

# Top-right header anchor coordinates (Canva design space)
HEADER_RIGHT_MARGIN_X = 765.0
HEADER_TOP_Y = 22.0
HEADER_FONT_SIZE = 33.2 * 1.15  # Scaled by 115% (~38.18pt)
PROVISIONAL_FONT_SIZE = 11.5 * 1.15  # Scaled by 115% (~13.23pt)

FONT_MAP = {
    "bold": FONTS_DIR / "Poppins-Bold.ttf",
    "semibold": FONTS_DIR / "Poppins-SemiBold.ttf",
    "regular": FONTS_DIR / "Poppins-Regular.ttf",
}

TEXT_COLOR_WHITE = (255, 255, 255, 255)
TEXT_COLOR_GOLD = (223, 177, 53, 255)


def get_canva_element_center(
    x: float, y: float, w: float, h: float, angle_deg: float
) -> tuple[float, float]:
    theta = math.radians(angle_deg)
    cos_t = abs(math.cos(theta))
    sin_t = abs(math.sin(theta))
    half_aabb_w = (w * cos_t + h * sin_t) / 2.0
    half_aabb_h = (w * sin_t + h * cos_t) / 2.0
    return x + half_aabb_w, y + half_aabb_h


def get_font(style: str, size: float, scale: float = 1.0) -> ImageFont.FreeTypeFont:
    clean_style = str(style).lower().strip()
    font_path = FONT_MAP.get(clean_style, FONT_MAP["regular"])
    return ImageFont.truetype(str(font_path), int(round(float(size) * scale)))


def wrap_text_to_width(
    text: str, font: ImageFont.FreeTypeFont, max_width: float, draw: ImageDraw.Draw
) -> list[str]:
    words = str(text).strip().split()
    if not words:
        return []

    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_w = bbox[2] - bbox[0]

        if line_w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def load_opponent_crest(
    opponent_name: str, max_w_px: int, max_h_px: int
) -> Image.Image | None:
    raw_name = opponent_name.strip()
    base_name = re.sub(
        r"\b(RFC|RUFC|WRFC|U\d+|WARRIORS|HURRICANES|BOYS|GIRLS)\b",
        "",
        raw_name,
        flags=re.IGNORECASE,
    ).strip()

    search_terms = {raw_name, base_name}
    candidates = []

    for term in search_terms:
        if not term:
            continue
        underscored = term.replace(" ", "_")
        hyphenated = term.replace(" ", "-")

        candidates.extend(
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

    for path in candidates:
        if path.exists():
            img = Image.open(path).convert("RGBA")
            img.thumbnail((max_w_px, max_h_px), Image.Resampling.LANCZOS)
            return img
    return None


def render_top_right_header(
    base_img: Image.Image,
    home_team: str,
    match_date: str,
    scale: float,
    is_provisional: bool = False,
):
    draw = ImageDraw.Draw(base_img)
    f_header = get_font("bold", HEADER_FONT_SIZE, scale)
    f_prov = get_font("bold", PROVISIONAL_FONT_SIZE, scale)

    right_x = HEADER_RIGHT_MARGIN_X * scale
    curr_y = HEADER_TOP_Y * scale

    # Line 1: Home Team
    line1 = str(home_team).upper()
    bb1 = draw.textbbox((0, 0), line1, font=f_header)
    w1 = bb1[2] - bb1[0]
    h1 = bb1[3] - bb1[1]
    draw.text((right_x - w1 - bb1[0], curr_y - bb1[1]), line1, font=f_header, fill=TEXT_COLOR_WHITE)
    curr_y += h1 + int(4.0 * scale)

    # Line 2: HRFC PITCHES
    line2 = "HRFC PITCHES"
    bb2 = draw.textbbox((0, 0), line2, font=f_header)
    w2 = bb2[2] - bb2[0]
    h2 = bb2[3] - bb2[1]
    draw.text((right_x - w2 - bb2[0], curr_y - bb2[1]), line2, font=f_header, fill=TEXT_COLOR_WHITE)
    curr_y += h2 + int(4.0 * scale)

    # Optional "PROVISIONAL" sub-tag
    if is_provisional:
        line_prov = "PROVISIONAL"
        bb_p = draw.textbbox((0, 0), line_prov, font=f_prov)
        wp = bb_p[2] - bb_p[0]
        hp = bb_p[3] - bb_p[1]
        draw.text((right_x - wp - bb_p[0], curr_y - bb_p[1]), line_prov, font=f_prov, fill=TEXT_COLOR_GOLD)
        curr_y += hp + int(2.0 * scale)

    # Line 3: Match Date
    line3 = str(match_date).strip()
    bb3 = draw.textbbox((0, 0), line3, font=f_header)
    w3 = bb3[2] - bb3[0]
    draw.text((right_x - w3 - bb3[0], curr_y - bb3[1]), line3, font=f_header, fill=TEXT_COLOR_GOLD)


def generate_pitch_map(
    config_excel_path: Path,
    pitch_key: str,
    home_team: str,
    opponent: str,
    ko_time: str,
    match_date: str = "19.04.26",
    is_provisional: bool = False,
    output_filename: str = "output_pitch_map.png",
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    anchors_df = pd.read_excel(config_excel_path, sheet_name=0)

    target_clean = re.sub(r"[^A-Z0-9]", "", str(pitch_key).upper())
    anchors_df["clean_key"] = (
        anchors_df["pitch_key"].astype(str).str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
    )

    match = anchors_df[
        (anchors_df["clean_key"] == target_clean)
        | (anchors_df["clean_key"] == f"P{target_clean}")
        | (anchors_df["clean_key"] == f"PITCH{target_clean}")
        | (anchors_df["clean_key"] == target_clean.lstrip("P"))
        | (anchors_df["clean_key"] == target_clean.replace("PITCH", ""))
    ]

    if match.empty:
        available_keys = anchors_df["pitch_key"].dropna().tolist()
        raise ValueError(
            f"Pitch key '{pitch_key}' not found. Available keys in sheet: {available_keys}"
        )
    anchor = match.iloc[0].to_dict()

    base_image_path = MAPS_DIR / str(anchor["base_image"]).strip()
    if not base_image_path.exists():
        raise FileNotFoundError(f"Base map image not found: {base_image_path}")
    base_img = Image.open(base_image_path).convert("RGBA")

    scale = base_img.width / CANVA_DESIGN_WIDTH

    raw_x = float(anchor["x"])
    raw_y = float(anchor["y"])
    raw_w = float(anchor["width"])
    raw_h = float(anchor["height"])
    angle = float(anchor["angle"]) if "angle" in anchor and pd.notna(anchor["angle"]) else 0.0

    canva_cx, canva_cy = get_canva_element_center(raw_x, raw_y, raw_w, raw_h, angle)
    cx = canva_cx * scale
    cy = canva_cy * scale

    text_angle = -float(anchor["text_angle"]) if "text_angle" in anchor and pd.notna(anchor["text_angle"]) else 0.0
    max_w_allowed = raw_w * 0.75 * scale

    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    f_l1 = get_font(anchor["l1_style"] if "l1_style" in anchor else "bold", anchor["l1_size"], scale)
    f_l2 = get_font(anchor["l2_style"] if "l2_style" in anchor else "regular", anchor["l2_size"], scale)
    f_l3 = get_font(anchor["l3_style"] if "l3_style" in anchor else "semibold", anchor["l3_size"], scale)
    f_l4 = get_font(anchor["l4_style"] if "l4_style" in anchor else "regular", anchor["l4_size"], scale)

    home_lines = wrap_text_to_width(str(home_team).upper(), f_l1, max_w_allowed, dummy_draw)
    opp_lines = wrap_text_to_width(str(opponent).upper(), f_l3, max_w_allowed, dummy_draw)
    ko_lines = wrap_text_to_width(f"KO {ko_time}", f_l4, max_w_allowed, dummy_draw)

    text_items = []
    for hl in home_lines:
        text_items.append((hl, f_l1, float(anchor["l1_size"])))
    text_items.append(("v", f_l2, float(anchor["l2_size"])))
    for ol in opp_lines:
        text_items.append((ol, f_l3, float(anchor["l3_size"])))
    for kl in ko_lines:
        text_items.append((kl, f_l4, float(anchor["l4_size"])))

    metrics = []
    for txt, fnt, pt_size in text_items:
        ascent, descent = fnt.getmetrics()
        line_height = ascent + descent
        bbox = dummy_draw.textbbox((0, 0), txt, font=fnt)
        text_width = bbox[2] - bbox[0]
        gap_px = int(round(pt_size * scale * 0.18))
        metrics.append((txt, fnt, text_width, line_height, gap_px, bbox[0], bbox[1]))

    total_text_h = sum(m[3] + m[4] for m in metrics)
    max_line_w = max(m[2] for m in metrics)

    text_overlay = Image.new(
        "RGBA",
        (int(max_line_w + 30 * scale), int(total_text_h + 30 * scale)),
        (0, 0, 0, 0),
    )
    t_draw = ImageDraw.Draw(text_overlay)

    curr_y = int(15 * scale)
    for txt, fnt, line_w, line_h, gap_px, left_offset, top_offset in metrics:
        line_x = (text_overlay.width - line_w) // 2
        t_draw.text((line_x - left_offset, curr_y - top_offset), txt, font=fnt, fill=TEXT_COLOR_WHITE)
        curr_y += line_h + gap_px

    if text_angle != 0.0:
        rotated_text = text_overlay.rotate(
            text_angle, expand=True, resample=Image.Resampling.BICUBIC
        )
    else:
        rotated_text = text_overlay

    dest_x = int(round(cx - (rotated_text.width / 2.0)))
    dest_y = int(round(cy - (rotated_text.height / 2.0)))
    base_img.alpha_composite(rotated_text, dest=(dest_x, dest_y))

    max_crest_w = int(round(OPPONENT_BOX_W * scale))
    max_crest_h = int(round(OPPONENT_BOX_H * scale))
    crest_img = load_opponent_crest(opponent, max_crest_w, max_crest_h)

    if crest_img:
        crest_cx = OPPONENT_CREST_CX * scale
        crest_cy = OPPONENT_CREST_CY * scale
        crest_dest_x = int(round(crest_cx - (crest_img.width / 2.0)))
        crest_dest_y = int(round(crest_cy - (crest_img.height / 2.0)))
        base_img.alpha_composite(crest_img, dest=(crest_dest_x, crest_dest_y))

    render_top_right_header(
        base_img=base_img,
        home_team=home_team,
        match_date=match_date,
        scale=scale,
        is_provisional=is_provisional,
    )

    output_filepath = OUTPUT_DIR / output_filename
    base_img.convert("RGB").save(output_filepath, "PNG")

    print(f"Generated: {output_filepath}")
    return output_filepath


if __name__ == "__main__":
    config_file = BASE_DIR / "config.xlsx"

    generate_pitch_map(
        config_excel_path=config_file,
        pitch_key="P1_WHOLE",
        home_team="WARRIORS U14",
        opponent="CHINNOR RFC",
        ko_time="13:00",
        match_date="19.04.26",
        is_provisional=True,
        output_filename="test_p1_header.png",
    )