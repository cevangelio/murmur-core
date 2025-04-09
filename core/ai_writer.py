from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)
import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def generate_post(prompt):
    response = client.chat.completions.create(model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=1000,
    temperature=0.7)
    return response.choices[0].message.content