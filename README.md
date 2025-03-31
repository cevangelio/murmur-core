# murmur-core

_The mind of Murmur._

**murmur-core** is the engine behind the Murmur project. It takes structured or unstructured input—logs, RSS news, system events—and feeds it into an AI-powered pipeline. The output: polished markdown blog posts with proper frontmatter, ready to be published.

Think of it as an autonomous ghostwriter with access to your logs.

## Features

- Reads log data and news feeds
- Uses a custom prompt template to generate content via AI
- Formats output to Markdown with YAML frontmatter
- Supports multiple data sources and scheduling
- Built for plug-and-play with static site generators like Astro

## How It Works

1. **Input Source:** Pulls data from logs, RSS feeds, or any custom JSON/text format.
2. **AI Prompting:** Feeds context into an LLM with a structured prompt.
3. **Markdown Output:** Saves the result to `.md` files in the specified content directory.
4. **Optional Hooks:** Run post-generation hooks for Git commits, deployments, etc.

## Setup

```bash
git clone https://github.com/yourusername/murmur-core.git
cd murmur-core
cp .env.example .env  # Add your API keys and paths
pip install -r requirements.txt
```

## Usage

```bash
python generate_post.py
```

## Configuration

Edit the .env or config.yaml file to set:
- Input sources (log paths, RSS URLs)
- Output directory (your murmur-shell content folder)
- Prompt behavior
- AI model / key

## License
MIT

murmur-core hums quietly in the background. It never sleeps.
