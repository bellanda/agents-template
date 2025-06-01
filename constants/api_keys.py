import os

import dotenv

dotenv.load_dotenv()

KEYS = {
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
}

for key, value in KEYS.items():
    if value is None:
        raise ValueError(f"Environment variable {key} is not set")
