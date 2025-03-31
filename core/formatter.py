# core/formatter.py

def format_markdown(content):
    from datetime import datetime
    import re
    import slugify

    now = datetime.utcnow()
    pub_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Extract first line or fallback
    first_line = content.strip().split("\n")[0]
    title_raw = re.sub(r'[:"\\]', '', first_line.strip())
    title = title_raw if title_raw else "Auto-generated Post"

    # Slugify title
    slug = slugify.slugify(title)

    # Try to extract tags from content (if marked)
    tag_lines = [line for line in content.splitlines() if line.lower().startswith("tags:")]
    tags = []
    if tag_lines:
        try:
            tags_line = tag_lines[0].split(":", 1)[1].strip()
            tags = [t.strip() for t in tags_line.split(",") if t.strip()]
        except Exception:
            tags = []
    if not tags:
        tags = ["autopost", "murmur", "ai-generated"]

    description = "An automated blog post generated from logs and calendar events."

    tags_yaml = "\n".join([f"  - {tag}" for tag in tags])

    frontmatter = f"""---
author: Amber
pubDatetime: {pub_date}
modDatetime: {pub_date}
title: {title}
slug: {slug}
featured: false
draft: false
tags:
{tags_yaml}
description: {description}
---
"""
    return frontmatter + "\n" + content.strip()
