# core/formatter.py
from datetime import datetime, timezone,timedelta
import re
import yaml
from slugify import slugify
from pathlib import Path

# md_file = '/Users/cevangelio/Downloads/2025-04-17-forex-blog copy.md'

REQUIRED_FIELDS = ["author", "pubDatetime", "modDatetime", "title", "slug", "tags", "description"]
ISO8601_ZULU_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

def literal_str_presenter(dumper, data):
    """Avoid quoting ISO8601 datetime strings."""
    if ISO8601_ZULU_RE.match(data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style=None)
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, literal_str_presenter)
for ch in "0123456789":
    yaml.resolver.Resolver.yaml_implicit_resolvers.pop(ch, None)

def ensure_iso8601_string(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return value.strip('"')
    return str(value)

def validate_and_format_frontmatter(frontmatter_dict):
    """Ensure required fields are present and format YAML safely."""
    for field in REQUIRED_FIELDS:
        if field not in frontmatter_dict:
            raise ValueError(f"Missing required frontmatter field: '{field}'")

    # Let PyYAML handle formatting safely
    yaml_block = yaml.safe_dump(
        frontmatter_dict,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False
    )

    return yaml_block


def format_markdown(content):
    now = datetime.utcnow()
    pub_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Strip old frontmatter
    content_body = re.sub(r'^---\n.*?\n---\n+', '', content, flags=re.DOTALL).strip()
    # Extract existing frontmatter
    existing = extract_existing_frontmatter(content)

    # Prefer existing title if valid
    title = existing.get("title")
    if not title:
        first_line = content_body.split("\n")[0].strip()
        title = re.sub(r'^[#\s]*', '', first_line).strip()
        if not title:
            title = "Auto-generated Post"

    slug = existing.get("slug", slugify(title))

    # Prefer existing datetime values
    pub_datetime = ensure_iso8601_string(existing.get("pubDatetime", pub_date))
    mod_datetime = ensure_iso8601_string(existing.get("modDatetime", pub_date))

    # Tags
    tags = existing.get("tags", ["forex", "skyengine", "analysis", "algotrading"])
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    if not tags or not isinstance(tags, list):
        tags = ["forex", "skyengine", "analysis", "algotrading"]

    # Description
    try:
        description = content.split("\n")[9].split(":")[1].strip()
    except:
        description = ""
        
    frontmatter_dict = {
        "author": existing.get("author", "Amber"),
        "pubDatetime": pub_datetime,
        "modDatetime": mod_datetime,
        "title": title,
        "slug": slug,
        "featured": existing.get("featured", False),
        "draft": existing.get("draft", False),
        "tags": tags,
        "description": description
    }

    yaml_block = validate_and_format_frontmatter(frontmatter_dict)
    date_str = (datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')
    content_body = inject_chart_image(content_body, date_str)
    return f"---\n{yaml_block}---\n\n{content_body}"

def update_markdown_file(path):
    path = Path(path)
    if not path.exists() or not path.suffix == ".md":
        raise FileNotFoundError(f"Invalid markdown file: {path}")

    content = path.read_text(encoding='utf-8')

    # ⛔ DON'T strip frontmatter here — let format_markdown do it
    new_content = format_markdown(content)

    path.write_text(new_content, encoding='utf-8')
    print(f"✅ Updated frontmatter in {path.name}")


def extract_existing_frontmatter(raw_content):
    match = re.match(r'^---\n(.*?)\n---\n+', raw_content, flags=re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return {}
    return {}

def inject_chart_image(content_body: str, date_str: str) -> str:
    """
    Injects the chart <img> block before the '### Performance Drivers' section.
    """
    img_block = f"""
<div>
  <img src="/assets/pips_chart_{date_str}.png" class="w-full md:w-3/4 lg:w-2/3 mx-auto" alt="Basket Pips - {date_str}">
</div>
""".strip()

    injection_point = "### Performance Drivers"
    if injection_point in content_body:
        parts = content_body.split(injection_point, 1)
        return f"{parts[0].rstrip()}\n\n{img_block}\n\n{injection_point}{parts[1]}"
    else:
        print("⚠️  Injection point not found — skipping image injection.")
        return content_body