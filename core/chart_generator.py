import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from pathlib import Path
import json
from matplotlib.dates import DateFormatter
import matplotlib.lines as mlines
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageOps

mpl.rcParams['font.family'] = 'JetBrains Mono'
HOME = str(Path.home())
BLOG_ID = (datetime.now()-timedelta(days=1)).strftime('%B %d, %Y')
LOGO_PATH = f"{HOME}/Documents/MacTrader/SkyeFX/SkyEngine/assets/skyefx_logo.png"

def generate_basket_pips_chart(log_file_path, output_image_path):
    with open(log_file_path) as f:
        lines = f.readlines()

    records = [json.loads(line.strip()) for line in lines if line.strip()]
    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Filter only snapshots with pips
    snapshot_df = df[(df['type'] == 'snapshot') & df['pips'].notnull()].copy()
    snapshot_df["timestamp_15min"] = snapshot_df["timestamp"].dt.floor("15min")

    # Group by 15-minute intervals
    basket_pips_15min = snapshot_df.groupby("timestamp_15min")["pips"].sum().reset_index()

    # Extract news events
    news_events = df[df['type'] == 'news_event']
    if not news_events.empty and 'title' in news_events.columns:
        news_df = news_events[['timestamp', 'title']]
    else:
        news_df = pd.DataFrame(columns=['timestamp', 'title'])

    # Ensure no duplicate events
    news_df = news_df.drop_duplicates(subset=["timestamp", "title"])

    # Assign a unique color per event type
    unique_events = news_df['title'].unique()
    event_colors = plt.cm.tab10.colors[:len(unique_events)]
    color_map = dict(zip(unique_events, event_colors))

    # Plot
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(basket_pips_15min["timestamp_15min"], basket_pips_15min["pips"], marker='o', label='Total Basket Pips')

    # Plot news lines
    for _, row in news_df.iterrows():
        if row['title'] in color_map:
            ax.axvline(row['timestamp'], color=color_map[row['title']], linestyle=':', linewidth=1.2, alpha=0.9)
        else:
            print(f"Missing color for event: {row['title']}")


    # Highlight highest and lowest points
    max_idx = basket_pips_15min['pips'].idxmax()
    min_idx = basket_pips_15min['pips'].idxmin()
    max_point = basket_pips_15min.loc[max_idx]
    min_point = basket_pips_15min.loc[min_idx]

    ax.annotate(
        f"High: {max_point['pips']:.1f} pips",
        xy=(max_point['timestamp_15min'], max_point['pips']),
        xytext=(5, 10),  # X and Y offset in points
        textcoords='offset points',
        ha='left', va='bottom',
        fontsize=9, color='green',
        arrowprops=dict(arrowstyle='-', color='green')
    )

    ax.annotate(
        f"Low: {min_point['pips']:.1f} pips",
        xy=(min_point['timestamp_15min'], min_point['pips']),
        xytext=(5, -15),
        textcoords='offset points',
        ha='left', va='top',
        fontsize=9, color='red',
        arrowprops=dict(arrowstyle='-', color='red')
    )

    # Adjust y-limits to make space for labels
    y_min, y_max = basket_pips_15min["pips"].min(), basket_pips_15min["pips"].max()
    y_range = y_max - y_min
    ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)

    # Format x-axis to 12h format, remove date
    ax.xaxis.set_major_formatter(DateFormatter("%I:%M %p"))

    # Legend setup for news events
    handles = [
    mlines.Line2D([], [], color=color_map[title], linestyle=':', label=title)
    for title in unique_events if title in color_map]
    ax.legend(handles=handles, loc='lower left', fontsize=8, title="News Events")

    ax.set_title(f"Total Basket Pips | {BLOG_ID}")
    ax.set_xlabel("Time")
    ax.set_ylabel("Basket Pips")
    ax.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_image_path)
    plt.close()
    print(f"Generated basket pips plot. Saved in {output_image_path}")

def slice_image_for_instagram(input_image_path, output_dir):
    """
    Slices a wide image into 3 parts, pads vertically to preserve top/bottom,
    and resizes each to 1080x1080 for Instagram.
    """
    img = Image.open(input_image_path)
    width, height = img.size
    part_width = width // 3

    for i in range(3):
        left = i * part_width
        right = (i + 1) * part_width if i < 2 else width
        cropped = img.crop((left, 0, right, height))

        # Pad to square (vertically)
        square_size = max(cropped.size)
        padded = ImageOps.pad(cropped, (square_size, square_size), method=Image.BICUBIC, color=(255, 255, 255))

        # Resize to Instagram square size
        resized = padded.resize((1080, 1080), Image.LANCZOS)

        output_path = Path(output_dir) / f"{Path(input_image_path).stem}_part{i+1}.png"
        resized.save(output_path)
        print(f"✅ Saved Instagram slice: {output_path}")


def generate_instagram_cover(output_path, title, total_pips, top_pairs, logo_path=None):
    # Create base image
    img = Image.new("RGB", (1080, 1080), color="#0f0f0f")
    draw = ImageDraw.Draw(img)

    # Load fonts (JetBrains Mono preferred)
    try:
        title_font = ImageFont.truetype("JetBrainsMono-Bold.ttf", 70)
        pips_font = ImageFont.truetype("JetBrainsMono-Regular.ttf", 50)
        small_font = ImageFont.truetype("JetBrainsMono-Regular.ttf", 40)
    except:
        title_font = ImageFont.load_default()
        pips_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Draw title
    draw.text((60, 200), title, font=title_font, fill="white")

    # Total gain
    draw.text((60, 320), f"Day High: {total_pips} pips", font=pips_font, fill="#00FF88")

    # Top pairs list
    y = 520
    for pair, gain in top_pairs:
        text = f"{pair:<8} {gain:+} pips"
        draw.text((60, y), text, font=small_font, fill="white")
        y += 70

    # Optional logo overlay
    if logo_path and Path(logo_path).exists():
        logo = Image.open(logo_path).convert("RGBA")
        # Resize to fit (e.g., 150x150 max)
        max_logo_size = (150, 150)
        logo.thumbnail(max_logo_size, Image.LANCZOS)

        # Paste in bottom-right with padding
        logo_x = img.width - logo.width - 40
        logo_y = img.height - logo.height - 40
        img.paste(logo, (logo_x, logo_y), mask=logo)

    # Save image
    output_path = Path(output_path)
    img.save(output_path)
    print(f"✅ Saved Instagram cover: {output_path}")

def generate_generic_instagram_cover(output_path, main_title, sub_title, logo_path=None):
    # Create base image
    img = Image.new("RGB", (1080, 1080), color="#0f0f0f")
    draw = ImageDraw.Draw(img)

    # Load fonts
    try:
        main_font = ImageFont.truetype("JetBrainsMono-Bold.ttf", 90)
        sub_font = ImageFont.truetype("JetBrainsMono-Regular.ttf", 55)
    except:
        main_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    # Helper: manually break text after N characters
    def draw_manual_break(draw, text, font, start_y, fill, max_chars=25, line_spacing=10):
        lines = []
        while len(text) > max_chars:
            # Find nearest space before max_chars
            break_pos = text.rfind(' ', 0, max_chars)
            if break_pos == -1:
                break_pos = max_chars
            lines.append(text[:break_pos])
            text = text[break_pos:].lstrip()
        lines.append(text)

        y = start_y
        for line in lines:
            draw.text((60, y), line, font=font, fill=fill)
            y += 90 + line_spacing  # vertical spacing after each line

    # Draw main title (white, bigger)
    draw.text((60, 200), main_title, font=main_font, fill="white")

    # Draw sub title (green, smaller)
    draw_manual_break(draw, sub_title, sub_font, start_y=540, fill="#00FF88", max_chars=40)

    # Optional logo overlay
    if logo_path and Path(logo_path).exists():
        logo = Image.open(logo_path).convert("RGBA")
        max_logo_size = (150, 150)
        logo.thumbnail(max_logo_size, Image.LANCZOS)

        logo_x = img.width - logo.width - 40
        logo_y = img.height - logo.height - 40
        img.paste(logo, (logo_x, logo_y), mask=logo)

    # Save image
    output_path = Path(output_path)
    img.save(output_path)
    print(f"✅ Saved Instagram cover: {output_path}")
