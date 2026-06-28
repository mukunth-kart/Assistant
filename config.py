import os
from dotenv import load_dotenv

# Resolve paths relative to the config file
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, ".env")

# Load environment variables
load_dotenv(env_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Simple validation warnings
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is not set. Ingestion and LLM modules will fail.")
if not TELEGRAM_BOT_TOKEN:
    print("WARNING: TELEGRAM_BOT_TOKEN is not set. Telegram bot will fail to start.")
