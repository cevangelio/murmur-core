import os
import shutil
import datetime

def rename_and_move_blog_file(download_dir, blog_dest, date_str=None):
    """
    Looks for blog_post.md in the download folder,
    renames it to trade_summary_YYYY-MM-DD.md,
    and moves it to the destination folder.
    """
    download_dir = os.path.expanduser(download_dir)
    blog_dest = os.path.expanduser(blog_dest)

    # Find downloaded blog post
    candidates = [f for f in os.listdir(download_dir) if "blog_post" in f and f.endswith(".md")]
    if not candidates:
        print("⚠️ No blog_post markdown found.")
        return

    original = max(candidates, key=lambda f: os.path.getctime(os.path.join(download_dir, f)))
    original_path = os.path.join(download_dir, original)

    # Use today’s date unless specified
    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    new_filename = f"trade_summary_{date_str}.md"
    new_path = os.path.join(blog_dest, new_filename)

    shutil.move(original_path, new_path)
    print(f"✅ Renamed and moved: {original} → {new_filename}")
