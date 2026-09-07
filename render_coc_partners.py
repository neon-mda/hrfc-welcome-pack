from pathlib import Path
from functools import lru_cache
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
COVERS_DIR = ASSETS_DIR / "covers"
MAPS_DIR = ASSETS_DIR / "maps"
OUTPUT_DIR = BASE_DIR / "output"

@lru_cache(maxsize=16)
def get_cached_base_image(image_path_str: str) -> Image.Image:
    return Image.open(image_path_str).convert("RGBA")

def resolve_static_template_path(page_type: str, home_team: str) -> Path:
    clean = str(home_team).strip().upper()
    prefix = "DEFAULT"
    if "WARRIOR" in clean:
        prefix = "WARRIORS"
    elif "HURRICANE" in clean:
        prefix = "HURRICANES"

    candidates = [
        COVERS_DIR / f"{page_type}_{prefix}.png",
        COVERS_DIR / f"{page_type}_DEFAULT.png",
        COVERS_DIR / f"{page_type}.png",
        MAPS_DIR / f"{page_type}_{prefix}.png",
        MAPS_DIR / f"{page_type}.png",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Static template '{page_type}' not found for prefix '{prefix}'.")

def generate_static_page(
    home_team: str,
    page_type: str,
    output_filename: str,
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    template_path = resolve_static_template_path(page_type, home_team)
    img = get_cached_base_image(str(template_path.resolve())).copy()
    
    output_filepath = OUTPUT_DIR / output_filename
    img.convert("RGB").save(output_filepath, "PNG")
    return output_filepath

def generate_chairwelcome_page(home_team: str, output_filename: str = "output_chairwelcome.png") -> Path:
    return generate_static_page(home_team, "CHAIRWELCOME", output_filename)

def generate_coc_page(home_team: str, output_filename: str = "output_coc.png") -> Path:
    return generate_static_page(home_team, "COC", output_filename)

def generate_partners_page(home_team: str, output_filename: str = "output_partners.png") -> Path:
    return generate_static_page(home_team, "PARTNERS", output_filename)