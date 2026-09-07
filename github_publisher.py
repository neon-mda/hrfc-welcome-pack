import subprocess
import os
import shutil

def get_git_path():
    """Finds the git executable path on Windows automatically."""
    git_path = shutil.which("git")
    if git_path:
        return git_path
    
    # Common default installation paths for Git on Windows
    common_paths = [
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files\Cmd\git.exe",
        r"C:\Users\\AppData\Local\Programs\Git\cmd\git.exe"
    ]
    for path in common_paths:
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded):
            return expanded
            
    return "git" # Fallback

def publish_pdf_to_github(pdf_path: str, filename: str) -> str:
    """Copies PDF to published_fixtures folder, commits, pushes, and returns raw GitHub URL."""
    target_dir = "published_fixtures"
    os.makedirs(target_dir, exist_ok=True)
    destination = os.path.join(target_dir, filename)
    
    # Copy file into the local repo directory
    with open(pdf_path, "rb") as src, open(destination, "wb") as dst:
        dst.write(src.read())
        
    git_cmd = get_git_path()
    
    # Run git commands securely with explicit executable path
    subprocess.run([git_cmd, "add", destination], check=True)
    
    status_result = subprocess.run([git_cmd, "status", "--porcelain"], capture_output=True, text=True)
    if filename in status_result.stdout or destination in status_result.stdout:
        subprocess.run([git_cmd, "commit", "-m", f"Auto-publish fixture asset: {filename}"], check=True)
        subprocess.run([git_cmd, "push", "origin", "main"], check=True)
    
    # REPLACE WITH YOUR ACTUAL GITHUB USERNAME
    repo_owner = "your-github-username"
    repo_name = "hrfc-welcome-pack"
    
    return f"https://raw.githubusercontent.com/{repo_owner}/{repo_name}/main/{target_dir}/{filename}"