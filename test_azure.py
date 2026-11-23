"""
Test the Azure OpenAI deployment before using it in the pipeline.
Run: python test_azure.py
"""
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    base_url=os.environ["AZURE_OPENAI_BASE_URL"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
)
MODEL = os.environ["AZURE_OPENAI_DEPLOYMENT"]
print("Base URL  :", os.environ["AZURE_OPENAI_BASE_URL"])
print("Deployment:", MODEL)

# TEST 1 - does the key and endpoint work?
try:
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Reply with the single word OK."}],
    )
    print("\nTEST 1 OK :", r.choices[0].message.content, "| model:", r.model)
except Exception as e:
    print("\nTEST 1 FAILED:", e)
    raise SystemExit

# TEST 2 - JSON mode (our scripts need this)
try:
    r = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content":
                   'Is "Table 1 Soil properties at sowing" useful for a soil model? '
                   'Return JSON: {"use": "input" or "not_needed", "reason": "short"}'}],
    )
    print("TEST 2 OK :", json.loads(r.choices[0].message.content))
except Exception as e:
    print("TEST 2 FAILED:", e)

# TEST 3 - is temperature=0 accepted? (reasoning models often refuse it)
try:
    client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[{"role": "user", "content": "Reply with OK."}],
    )
    print("TEST 3 OK : temperature=0 is accepted")
except Exception as e:
    print("TEST 3 - temperature=0 NOT accepted:", e)