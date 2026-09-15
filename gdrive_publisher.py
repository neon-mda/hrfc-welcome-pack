import os
import shutil

def publish_pdf_to_gdrive(pdf_path: str, filename: str) -> str:
    """Copies the compiled PDF directly into the local Google Drive sync folder with verification."""
    gdrive_target_dir = r"G:\My Drive\HRFC\HRFC_Matchday_Output"
    
    # Check if the G: drive is mounted/available (avoiding trailing backslash escape issues)
    if not os.path.exists(r"G:"):
        raise RuntimeError("Drive G: is not detected or mounted on this system.")
        
    # Ensure the destination folder exists
    os.makedirs(gdrive_target_dir, exist_ok=True)
    destination = os.path.join(gdrive_target_dir, filename)
    
    # Copy file into Google Drive
    shutil.copy(pdf_path, destination)
    
    # Verify it actually landed there
    if not os.path.exists(destination):
        raise FileNotFoundError(f"Failed to copy file to Google Drive destination: {destination}")
        
    return destination