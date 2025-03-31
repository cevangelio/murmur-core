import os
import logging
from dotenv import load_dotenv
from core.input_reader import read_logs
from core.prompt_builder import build_prompt
from core.ai_writer import generate_post
from core.formatter import format_markdown
from core.post_saver import save_post

# Setup logging
logging.basicConfig(filename='murmur.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s:%(message)s')

load_dotenv()

LOG_DIR = os.getenv("LOG_DIR")
MURMUR_SHELL_PATH = os.getenv("MURMUR_SHELL_PATH")
PROMPT_TEMPLATE = os.getenv("DEFAULT_PROMPT")

def main():
    try:
        logging.info("Starting murmur-core pipeline")
        logs = read_logs(LOG_DIR)
        logging.info("Logs read successfully")

        prompt = build_prompt(logs, PROMPT_TEMPLATE)
        logging.info("Prompt built successfully")

        ai_response = generate_post(prompt)
        logging.info("AI response received")

        markdown = format_markdown(ai_response)
        logging.info("Markdown formatted")

        saved_path = save_post(markdown, MURMUR_SHELL_PATH)
        logging.info(f"Post saved to {saved_path}")

    except Exception as e:
        logging.error(f"Error during murmur-core run: {e}")
        raise

if __name__ == "__main__":
    main()