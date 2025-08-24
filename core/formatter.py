# core/formatter.py
# -*- coding: utf-8 -*-
from datetime import datetime, timezone, timedelta
import re
import yaml
from slugify import slugify
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Regexes & constants
# ──────────────────────────────────────────────────────────────────────────────

REQUIRED_FIELDS = [
    "author", "pubDatetime", "modDatetime", "title", "slug",
    "tags", "description"
]

FRONTMATTER_RE = re.compile(
    r'^\s*---\s*\n(.*?)\n---\s*(?:\n|$)',
    flags=re.DOTALL | re.MULTILINE
)

H1_RE          = re.compile(r'^\s*#\s+(.+?)\s*$', re.MULTILINE)
ISO8601_Z_RE   = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

PERF_H3_PAT    = re.compile(r'^\s*###\s+Performance\s+Drivers\s*$', re.IGNORECASE)
TABLE_ROW_PAT  = re.compile(r'^\s*\|.*\|\s*$')

CANON_TABLE_HEADER = "| Currency Pair | Starting Pips | Ending Pips |"
CANON_TABLE_RULE   = "| --- | ---: | ---: |"

# ──────────────────────────────────────────────────────────────────────────────
# YAML style: keep ISO strings unquoted (same behavior you had)
# ──────────────────────────────────────────────────────────────────────────────

def _literal_str_presenter(dumper, data):
    if ISO8601_Z_RE.match(data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style=None)
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, _literal_str_presenter)
# Keep numbers as strings when needed (same as your previous behavior)
for ch in "0123456789":
    yaml.resolver.Resolver.yaml_implicit_resolvers.pop(ch, None)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _iso_now_z():
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

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

def extract_existing_frontmatter(raw_content: str) -> dict:
    m = FRONTMATTER_RE.search(raw_content)
    if m:
        try:
            return yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            return {}
    return {}

def strip_frontmatter(raw_content: str) -> str:
    return FRONTMATTER_RE.sub("", raw_content, count=1).lstrip()

def _first_h1_and_body(md: str):
    """
    Return (title_from_h1 or None, body starting from the H1 if present, else original).
    """
    m = H1_RE.search(md)
    if not m:
        return None, md.strip()
    title = m.group(1).strip()
    body_from_h1 = md[m.start():].lstrip()
    return title, body_from_h1

def _first_paragraph_after_h1(md_from_h1: str) -> str:
    """
    Given text that starts with '# Title', return the first non-empty paragraph
    after that H1 (skip headings/rules/tables/lists/code/html). Used for description.
    """
    lines = md_from_h1.splitlines()
    # remove the H1 line itself
    if lines and lines[0].lstrip().startswith("# "):
        lines = lines[1:]

    i = 0
    # skip blanks, headings, rules, list/table/html/fence lines
    while i < len(lines):
        s = lines[i].strip()
        if (
            not s or s.startswith("#") or s in ("---", "***")
            or s.startswith(("|", "-", "*", "+", ">", "<", "```"))
        ):
            i += 1
            continue
        break

    # gather paragraph until a structural break
    para = []
    while i < len(lines) and lines[i].strip():
        s = lines[i].strip()
        if s.startswith(("|", "-", "*", "+", ">", "<", "```", "#")):
            break
        para.append(s)
        i += 1

    desc = " ".join(para).strip()
    if len(desc) > 200:
        desc = desc[:197].rstrip() + "..."
    return desc


def _validate_and_format_frontmatter(frontmatter_dict: dict) -> str:
    for field in REQUIRED_FIELDS:
        if field not in frontmatter_dict:
            raise ValueError(f"Missing required frontmatter field: '{field}'")
    return yaml.safe_dump(
        frontmatter_dict,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False
    )

def inject_chart_image(content_body: str, date_str: str) -> str:
    """
    Inject the chart <img> block immediately before '### Performance Drivers',
    but only if the same chart for the given date is not already present.
    """
    # If we've already injected this exact image for this date, skip
    img_signature = f"/assets/pips_chart_{date_str}.png"
    if img_signature in content_body:
        return content_body  # already present; idempotent

    img_block = f"""
<div>
  <img src="{img_signature}" class="w-full md:w-3/4 lg:w-2/3 mx-auto" alt="Basket Pips - {date_str}">
</div>
""".strip()

    lines = content_body.splitlines()

    # Find "### Performance Drivers" header
    h_idx = -1
    for i, ln in enumerate(lines):
        if PERF_H3_PAT.match(ln):
            h_idx = i
            break
    if h_idx == -1:
        print("⚠️  Injection point not found — skipping image injection.")
        return content_body

    before = lines[:h_idx]
    after  = lines[h_idx:]

    # ensure one blank line before/after the block for clean markdown rendering
    out = []
    out.extend(before)
    if out and out[-1].strip():
        out.append("")
    out.append(img_block)
    out.append("")
    out.extend(after)

    return "\n".join(out).strip() + "\n"


def _ensure_performance_table(body: str) -> str:
    """
    Inside '### Performance Drivers', ensure there is exactly ONE canonical
    header + alignment row, and DO NOT duplicate if it already exists.
    If a table is present without a header, insert the header above the first row.
    """
    def norm_row(s: str) -> str:
        # normalize a pipe row for comparison: lowercase, trim cells, collapse spaces
        s = s.strip().strip("|")
        parts = [re.sub(r"\s+", " ", p.strip().lower()) for p in s.split("|")]
        return "|".join(parts)

    canon_hdr_norm = norm_row(CANON_TABLE_HEADER)
    canon_rule_norm = norm_row(CANON_TABLE_RULE)

    lines = body.splitlines()

    # 1) Find '### Performance Drivers' section bounds
    h_idx = -1
    for i, ln in enumerate(lines):
        if PERF_H3_PAT.match(ln):
            h_idx = i
            break
    if h_idx == -1:
        return body

    end = len(lines)
    for j in range(h_idx + 1, len(lines)):
        if lines[j].lstrip().startswith("### "):
            end = j
            break

    sec = lines[h_idx+1:end]
    if not sec:
        return body

    # 2) Detect existing rows and any existing header occurrences
    first_table_idx = -1
    header_positions = []
    for k, ln in enumerate(sec):
        if not TABLE_ROW_PAT.match(ln.strip()):
            continue
        if first_table_idx == -1:
            first_table_idx = k
        if norm_row(ln) == canon_hdr_norm:
            header_positions.append(k)

    if first_table_idx == -1:
        # No table rows detected; leave as-is
        return body

    new_sec = sec[:]

    if header_positions:
        # 3a) A header already exists: keep the FIRST one, remove duplicates, and ensure one rule under it
        keep_idx = header_positions[0]

        # Remove any duplicate header lines (from bottom up to preserve indices)
        for idx in reversed(header_positions[1:]):
            del new_sec[idx]

        # After potential deletions, recompute keep_idx context
        # Ensure there is exactly ONE alignment rule right after the header
        if keep_idx + 1 >= len(new_sec) or norm_row(new_sec[keep_idx + 1]) != canon_rule_norm:
            # If there is an existing rule (non-canonical), replace it; otherwise insert
            if keep_idx + 1 < len(new_sec) and ("---" in new_sec[keep_idx + 1]):
                new_sec[keep_idx + 1] = CANON_TABLE_RULE
            else:
                new_sec.insert(keep_idx + 1, CANON_TABLE_RULE)

        # Also remove any additional alignment rules immediately following (duplicate rules)
        i = keep_idx + 2
        while i < len(new_sec) and new_sec[i].strip().startswith("|") and "---" in new_sec[i]:
            # Remove extra rule lines
            del new_sec[i]

    else:
        # 3b) Table present but no canonical header detected: insert header+rule BEFORE the first table row
        insert_at = first_table_idx
        new_sec.insert(insert_at, CANON_TABLE_RULE)
        new_sec.insert(insert_at, CANON_TABLE_HEADER)

    # 4) Reassemble the document
    out = lines[:h_idx+1] + new_sec + lines[end:]
    return "\n".join(out).strip() + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def format_markdown(content: str) -> str:
    """
    Normalize an LLM Markdown report for your Astro blog:
      - remove any existing frontmatter
      - use the first H1 as canonical title (or synthesize)
      - generate clean YAML frontmatter with your exact shape
      - keep body as produced by the model (new prompt enforces structure)
      - ensure Performance Drivers table header exists
      - inject chart image before Performance Drivers (yesterday's date)
    """
    if not content or not content.strip():
        return content

    now_iso = _iso_now_z()

    # 1) Parse & strip any existing frontmatter
    existing = extract_existing_frontmatter(content)
    body     = strip_frontmatter(content)

    # 2) Title via first H1 (preferred)
    title_from_h1, body_from_h1 = _first_h1_and_body(body)
    if title_from_h1:
        title = title_from_h1
        body  = body_from_h1
    else:
        # Fallback: first non-empty line
        first_line = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        title = first_line.strip("# ").strip() or "Auto-generated Post"
        # Ensure an H1 exists at top
        body = f"# {title}\n\n{body.lstrip()}"

    # 3) Description = first paragraph after H1
    # 3) Description: keep existing if present; otherwise derive from first paragraph after H1
    existing_desc = (existing.get("description") or "").strip()
    if existing_desc:
        description = existing_desc
    else:
        description = _first_paragraph_after_h1(body) or "Daily FX market movements and macro highlights."

    # 4) Frontmatter fields
    pub_datetime = ensure_iso8601_string(existing.get("pubDatetime", now_iso))
    mod_datetime = ensure_iso8601_string(existing.get("modDatetime", now_iso))
    slug         = existing.get("slug", slugify(title))
    tags         = existing.get("tags", ["forex", "skyengine", "analysis", "algotrading"])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, list) or not tags:
        tags = ["forex", "skyengine", "analysis", "algotrading"]

    fm = {
        "author":    existing.get("author", "Amber"),
        "pubDatetime": pub_datetime,
        "modDatetime": mod_datetime,
        "title":     title,
        "slug":      slug,
        "featured":  existing.get("featured", False),
        "draft":     existing.get("draft", False),
        "tags":      tags,
        "description": description
    }
    yaml_block = _validate_and_format_frontmatter(fm)

    # 5) Light, safe normalizations that match the new prompt’s contract
    body = _ensure_performance_table(body)

    # 6) Inject chart image before Performance Drivers (yesterday date)
    date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    body = inject_chart_image(body, date_str)

    # 7) Assemble final doc
    return f"---\n{yaml_block}---\n\n{body}".rstrip() + "\n"

def update_markdown_file(path):
    path = Path(path)
    if not path.exists() or not path.suffix == ".md":
        raise FileNotFoundError(f"Invalid markdown file: {path}")

    raw = path.read_text(encoding='utf-8')
    new = format_markdown(raw)
    path.write_text(new, encoding='utf-8')
    print(f"✅ Updated frontmatter in {path.name}")