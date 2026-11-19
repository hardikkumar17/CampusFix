
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Load the API key from the project root .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY is missing from .env")

# Initialize Groq
llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    reasoning_format="hidden"
)

# Test the model
response = llm.invoke(
    "Explain what a campus maintenance AI agent does in two sentences."
)

print("\nGroq response:")
print(response.content)
