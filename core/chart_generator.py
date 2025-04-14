import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from pathlib import Path
import json
from matplotlib.dates import DateFormatter
import matplotlib.lines as mlines
from datetime import datetime, timedelta

mpl.rcParams['font.family'] = 'JetBrains Mono'
BLOG_ID = (datetime.now()-timedelta(days=1)).strftime('%B %d, %Y')

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

    # Assign a unique color per event type
    unique_events = news_df['title'].unique()
    event_colors = plt.cm.tab10.colors[:len(unique_events)]
    color_map = dict(zip(unique_events, event_colors))

    # Plot
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(basket_pips_15min["timestamp_15min"], basket_pips_15min["pips"], marker='o', label='Total Basket Pips')

    # Plot news lines
    for _, row in news_df.iterrows():
        ax.axvline(row['timestamp'], color=color_map[row['title']], linestyle=':', linewidth=1.2, alpha=0.9)

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
    handles = [mlines.Line2D([], [], color=color_map[title], linestyle=':', label=title) for title in unique_events]
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