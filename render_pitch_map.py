from pathlib import Path
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MAPS_DIR = ASSETS_DIR / "maps"
OUTPUT_DIR = BASE_DIR / "output"

# Font mappings
FONT_MAP = {
    "bold": FONTS_DIR / "Poppins-Bold.ttf",
    "semibold": FONTS_DIR / "Poppins-SemiBold.ttf",
    "regular": FONTS_DIR / "Poppins-Regular.ttf",
}

SAFE_TOP_OFFSET_PX = 20.0


def hex_to_rgba(hex_str: str, alpha: int = 255) -> tuple:
    hex_str = str(hex_str).lstrip("#")
    r, g, b = tuple(int(hex_str[i : i + 2], 16) for i in (0, 2, 4))
    return (r, g, b, alpha)


def get_font(style: str, size: float) -> ImageFont.FreeTypeFont:
    clean_style = str(style).lower().strip()
    font_path = FONT_MAP.get(clean_style, FONT_MAP["regular"])
    return ImageFont.truetype(str(font_path), int(round(float(size))))


def build_lines(
    anchor: dict,
    home_team: str,
    opponent: str,
    ko_time: str,
    max_w: float,
    draw: ImageDraw.ImageDraw,
) -> list:
    f_l1 = get_font(anchor["l1_style"], anchor["l1_size"])
    f_l2 = get_font(anchor["l2_style"], anchor["l2_size"])
    f_l3 = get_font(anchor["l3_style"], anchor["l3_size"])
    f_l4 = get_font(anchor["l4_style"], anchor["l4_size"])

    # Opponent text wrapping
    opp_words = str(opponent).upper().split(" ")
    opp_lines = []
    curr = ""
    for w in opp_words:
        test = f"{curr} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=f_l3)
        if (bbox[2] - bbox[0]) <= max_w:
            curr = test
        else:
            if curr:
                opp_lines.append(curr)
            curr = w
    if curr:
        opp_lines.append(curr)

    lines = []
    lines.append((str(home_team).upper(), f_l1))
    lines.append(("v", f_l2))
    for ol in opp_lines:
        lines.append((ol, f_l3))
    lines.append((f"KO {ko_time}", f_l4))

    return lines


def generate_pitch_map(
    config_excel_path: Path,
    pitch_key: str,
    home_team: str,
    opponent: str,
    ko_time: str,
    output_filename: str = "output_pitch_map.png",
    stream: str = "warriors",
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    anchors_df = pd.read_excel(config_excel_path, sheet_name="pitch_anchors")
    themes_df = pd.read_excel(config_excel_path, sheet_name="brand_themes")

    # Match row configuration
    anchor_rows = anchors_df[anchors_df["pitch_key"] == pitch_key]
    if anchor_rows.empty:
        raise ValueError(
            f"Pitch key '{pitch_key}' not found in 'pitch_anchors' sheet."
        )
    anchor = anchor_rows.iloc[0].to_dict()

    theme_rows = themes_df[
        themes_df["stream"].str.lower() == stream.lower().strip()
    ]
    if theme_rows.empty:
        raise ValueError(
            f"Brand theme stream '{stream}' not found in 'brand_themes' sheet."
        )
    theme = theme_rows.iloc[0].to_dict()

    # Load base image
    base_image_path = MAPS_DIR / str(anchor["base_image"]).strip()
    if not base_image_path.exists():
        raise FileNotFoundError(f"Base map image not found: {base_image_path}")
    base_img = Image.open(base_image_path).convert("RGBA")

    # Bounding box geometry
    x = float(anchor["x"])
    y = float(anchor["y"])
    w = float(anchor["width"])
    h = float(anchor["height"])
    text_angle = float(anchor["text_angle"])
    line_spacing = float(anchor["line_spacing"])

    # Safe visual centre taking 20px pitch tag into account
    usable_y = y + SAFE_TOP_OFFSET_PX
    usable_h = h - SAFE_TOP_OFFSET_PX
    cx = x + (w / 2.0)
    cy = usable_y + (usable_h / 2.0)

    # Styling colours
    pill_bg = hex_to_rgba(theme["pill_bg_hex"], alpha=220)
    pill_border = hex_to_rgba(theme["pill_border_hex"], alpha=255)
    text_color = hex_to_rgba(theme["text_hex"], alpha=255)

    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    pad_x, pad_y = 10, 6

    lines = build_lines(
        anchor=anchor,
        home_team=home_team,
        opponent=opponent,
        ko_time=ko_time,
        max_w=(w - (pad_x * 2)),
        draw=dummy_draw,
    )

    # Compute bounding boxes for each text line
    metrics = []
    for txt, fnt in lines:
        bb = dummy_draw.textbbox((0, 0), txt, font=fnt)
        metrics.append((txt, fnt, bb[2] - bb[0], bb[3] - bb[1]))

    gap = int(float(anchor["l1_size"]) * (line_spacing - 1.0))
    total_text_h = sum(m[3] for m in metrics) + (gap * (len(metrics) - 1))
    max_line_w = max(m[2] for m in metrics)

    badge_w = max_line_w + (pad_x * 2)
    badge_h = total_text_h + (pad_y * 2)

    # Construct badge container
    badge_img = Image.new("RGBA", (int(badge_w), int(badge_h)), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(badge_img)

    b_draw.rounded_rectangle(
        [(0, 0), (badge_w - 1, badge_h - 1)],
        radius=6,
        fill=pill_bg,
        outline=pill_border,
        width=2,
    )

    curr_y = pad_y
    for txt, fnt, line_w, line_h in metrics:
        line_x = (badge_w - line_w) // 2
        b_draw.text((line_x, curr_y), txt, font=fnt, fill=text_color)
        curr_y += line_h + gap

    # Rotate badge if pitch orientation requires it
    if text_angle != 0.0:
        rotated_badge = badge_img.rotate(
            -text_angle, expand=True, resample=Image.Resampling.BICUBIC
        )
    else:
        rotated_badge = badge_img

    dest_x = int(round(cx - (rotated_badge.width / 2.0)))
    dest_y = int(round(cy - (rotated_badge.height / 2.0)))

    # Composite and save
    base_img.alpha_composite(rotated_badge, dest=(dest_x, dest_y))
    output_filepath = OUTPUT_DIR / output_filename
    base_img.convert("RGB").save(output_filepath, "PNG")

    print(f"Generated: {output_filepath}")
    return output_filepath


if __name__ == "__main__":
    # Test execution
    config_file = BASE_DIR / "config.xlsx"

    generate_pitch_map(
        config_excel_path=config_file,
        pitch_key="P2_BOTTOM",
        home_team="WARRIORS U16",
        opponent="BASINGSTOKE RFC",
        ko_time="11:15",
        output_filename="test_p2_bottom.png",
        stream="warriors",
    )