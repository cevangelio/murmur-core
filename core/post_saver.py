import subprocess
import os
import datetime

def git_commit_and_push(repo_dir, files, date_str=None):
    """
    Adds, commits, and pushes a list of files to the repo.
    """
    repo_dir = os.path.expanduser(repo_dir)
    os.chdir(repo_dir)

    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        for file in files:
            file_path = os.path.expanduser(file)
            subprocess.run(["git", "add", file_path], check=True)

        commit_message = f"New blog {date_str}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print(f"✅ Pushed files to repo: {files}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git command failed: {e}")
