from pathlib import Path
from PIL import Image

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

def compile_fixture_pdf(
    image_paths: list[Path],
    output_filename: str = "output_fixture.pdf"
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_filepath = OUTPUT_DIR / output_filename
    
    valid_imgs = []
    for p in image_paths:
        if p and Path(p).exists():
            img = Image.open(p).convert("RGB")
            if img.size != (1920, 1080):
                img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
            valid_imgs.append(img)
            
    if not valid_imgs:
        raise ValueError("No valid images provided for PDF compilation.")
        
    valid_imgs[0].save(
        output_filepath,
        "PDF",
        save_all=True,
        append_images=valid_imgs[1:],
        resolution=72.0,
        quality=100,
        subsampling=0,
        optimize=False,
        pagesize=(1920.0, 1080.0)
    )
    return output_filepath