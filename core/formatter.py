# core/formatter.py
from datetime import datetime
import re
import yaml
from slugify import slugify

REQUIRED_FIELDS = ["author", "pubDatetime", "modDatetime", "title", "slug", "tags", "description"]

def sanitize_frontmatter_value(value):
    """Wrap special values in quotes to avoid YAML issues."""
    if isinstance(value, str):
        if re.search(r'^[\*&]|[:{}[\],&*#?|\-<>=!%@`]', value.strip()):
            return f'"{value}"'
    return value

def validate_and_format_frontmatter(frontmatter_dict):
    """Ensure required fields are present and YAML-safe."""
    for field in REQUIRED_FIELDS:
        if field not in frontmatter_dict:
            raise ValueError(f"Missing required frontmatter field: '{field}'")

    safe_dict = {k: sanitize_frontmatter_value(v) for k, v in frontmatter_dict.items()}
    yaml_block = yaml.dump(safe_dict, default_flow_style=False, allow_unicode=True)
    try:
        yaml.safe_load(yaml_block)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in frontmatter: {e}")
    return yaml_block

def format_markdown(content):
    now = datetime.utcnow()
    pub_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Extract title
    first_line = content.strip().split("\n")[0]
    title_raw = re.sub(r'[:"\\]', '', first_line.strip())
    title = title_raw if title_raw else "Auto-generated Post"

    # Slugify title
    slug = slugify(title)

    # Extract tags
    tag_lines = [line for line in content.splitlines() if line.lower().startswith("tags:")]
    tags = []
    if tag_lines:
        try:
            tags_line = tag_lines[0].split(":", 1)[1].strip()
            tags = [t.strip() for t in tags_line.split(",") if t.strip()]
        except Exception:
            tags = []
    if not tags:
        tags = ["forex", "skyengine", "analysis", "algotrading"]

    # Extract description
    content_lines = content.strip().splitlines()
    desc_lines = []
    for line in content_lines[1:]:
        if line.strip() == "" or line.lower().startswith("tags:"):
            continue
        desc_lines.append(line.strip())
        if len(desc_lines) >= 2:
            break
    description = " ".join(desc_lines).strip()
    if not description or len(description) < 30:
        description = "A summary of daily trading performance based on forex snapshot logs."

    # Build frontmatter dict
    frontmatter_dict = {
        "author": "Amber",
        "pubDatetime": pub_date,
        "modDatetime": pub_date,
        "title": title,
        "slug": slug,
        "featured": False,
        "draft": False,
        "tags": tags,
        "description": description
    }

    # Convert to YAML frontmatter string
    yaml_block = validate_and_format_frontmatter(frontmatter_dict)

    return f"---\n{yaml_block}---\n\n{content.strip()}"