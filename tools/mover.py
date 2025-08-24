import os
import shutil
import datetime
from pathlib import Path

def rename_and_move_blog_file(download_dir, blog_dest, file_name, date_str=None):
    """
    Rename & move the most relevant markdown file from `download_dir` into `blog_dest`.

    Selection priority (newest wins within each bucket):
      1) trade_summary_*.md
      2) blog_post*.md
      3) any *.md (newest)

    New name = {file_name}_{YYYY-MM-DD}.md  (e.g., trade_summary_2025-08-23.md)

    Returns: destination path (str) if moved, or None if nothing found.
    """
    download_dir = os.path.expanduser(download_dir)
    blog_dest = os.path.expanduser(blog_dest)
    Path(blog_dest).mkdir(parents=True, exist_ok=True)

    if not os.path.isdir(download_dir):
        print(f"⚠️ Source directory not found: {download_dir}")
        return None

    # Gather candidates
    all_md = [f for f in os.listdir(download_dir) if f.lower().endswith(".md")]
    if not all_md:
        print("⚠️ No markdown files found to move.")
        return None

    def newest(paths):
        return max(paths, key=lambda f: os.path.getctime(os.path.join(download_dir, f)))

    # Priority buckets
    ts_candidates = [f for f in all_md if f.startswith("trade_summary_")]
    bp_candidates = [f for f in all_md if f.startswith("blog_post")]

    if ts_candidates:
        original = newest(ts_candidates)
    elif bp_candidates:
        original = newest(bp_candidates)
    else:
        # Fallback: newest .md in the directory
        original = newest(all_md)

    original_path = os.path.join(download_dir, original)

    # Date for new filename
    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    new_filename = f"{file_name}_{date_str}.md"   # e.g., "trade_summary_2025-08-23.md"
    new_path = os.path.join(blog_dest, new_filename)

    # If destination exists, overwrite (atomic-ish replace)
    try:
        if os.path.exists(new_path):
            os.remove(new_path)
    except Exception:
        pass

    shutil.move(original_path, new_path)
    print(f"✅ Renamed and moved: {original} → {new_filename}")
    return new_path