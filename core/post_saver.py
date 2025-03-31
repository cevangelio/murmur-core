import os
import subprocess
from datetime import datetime

def save_post(markdown, output_dir):
    date = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"{date}-murmur-post.md"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w") as f:
        f.write(markdown)

    # Git add, commit, and optionally push
    try:
        subprocess.run(["git", "add", filepath], cwd=output_dir, check=True)
        subprocess.run(["git", "commit", "-m", f"chore: add post for {date}"], cwd=output_dir, check=True)
        # subprocess.run(["git", "push"], cwd=output_dir, check=True)  # Uncomment to auto-push
    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e}")

    return filepath