import os

import dotenv

dotenv.load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
