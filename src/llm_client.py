"""
Shared AI connection for the three AI steps.

Which model is used is set in .env:
    LLM_PROVIDER=goedel   -> DeepSeek v4.1 Flash via Goedel Machines (GOEDEL_API_KEY)
    LLM_PROVIDER=azure    -> Azure OpenAI deployment (AZURE_OPENAI_API_KEY,
                             AZURE_OPENAI_BASE_URL, AZURE_OPENAI_DEPLOYMENT)

Both use the same OpenAI-compatible client, so the scripts stay the same.
"""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
PROVIDER = os.environ.get("LLM_PROVIDER", "goedel").strip().lower()

if PROVIDER == "azure":
    MODEL = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    TEMPERATURE = "default (1)"   # this model rejects temperature=0 (tested in test_azure.py)
elif PROVIDER == "goedel":
    MODEL = "deepseek/deepseek-v4.1-flash"
    TEMPERATURE = 0               # 0 = most repeatable answers
else:
    raise SystemExit(f"Unknown LLM_PROVIDER '{PROVIDER}' in .env (use goedel or azure)")


def make_client():
    """Client for the chosen provider."""
    if PROVIDER == "azure":
        return OpenAI(base_url=os.environ["AZURE_OPENAI_BASE_URL"],
                      api_key=os.environ["AZURE_OPENAI_API_KEY"])
    return OpenAI(base_url="https://api.goedelmachines.com/v1",
                  api_key=os.environ["GOEDEL_API_KEY"])


def model_kwargs():
    """Model settings for each request (temperature only where the model accepts it)."""
    if isinstance(TEMPERATURE, (int, float)):
        return {"model": MODEL, "temperature": TEMPERATURE}
    return {"model": MODEL}
