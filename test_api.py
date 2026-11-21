"""
API connection test for the Goedel Machines API (DeepSeek-V4.1-Flash).

Test 1: Does the key work?          -> send "hello", get an answer
Test 2: Can it return clean JSON?   -> needed for Step 2b (caption classification)

Usage:
    python src/test_api.py
"""
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

# ---- Settings ----
BASE_URL = "https://api.goedelmachines.com/v1"
MODEL = "deepseek/deepseek-v4.1-flash"

# ---- Load the key from .env (never print the key itself) ----
load_dotenv()
api_key = os.getenv("GOEDEL_API_KEY")
if not api_key:
    raise SystemExit("ERROR: GOEDEL_API_KEY not found in .env")
print(f"Key found (starts with {api_key[:10]}...)")

client = OpenAI(base_url=BASE_URL, api_key=api_key)


# =====================================================================
# TEST 1 - Does the key work?
# =====================================================================
print("\n--- TEST 1: hello ---")
resp = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "Reply with just the word: hello"}],
    temperature=0,          # 0 = same answer every time (repeatable)
)
print("Answer :", resp.choices[0].message.content)
print("Tokens :", resp.usage.prompt_tokens, "in /", resp.usage.completion_tokens, "out")


# =====================================================================
# TEST 2 - Can it return clean JSON?
# We use one real caption (Fig 8) as the example.
# =====================================================================
print("\n--- TEST 2: JSON output ---")
caption = ("Fig. 8. Grain weight under selected tillage practices during 2009 "
           "and 2010. Values are mean ± 1SE (n = 3).")

prompt = f"""You classify table/figure captions from agricultural field-experiment papers.
Return ONLY a JSON object with these keys:
  "type":     "caption" or "mention"
  "needed":   true or false  (needed as input data for the DayCent model?)
  "category": one of "site", "initial_soil", "crop_yield", "tillage",
              "fertiliser", "irrigation", "end_soil", "none"
  "reason":   one short sentence

Caption: {caption}"""

messages = [{"role": "user", "content": prompt}]

# First try the strict JSON mode. If the API does not support it, try without it.
try:
    resp = client.chat.completions.create(
        model=MODEL, messages=messages, temperature=0,
        response_format={"type": "json_object"},
    )
    mode = "JSON mode (response_format)"
except Exception as e:
    print("JSON mode not supported:", e)
    resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0)
    mode = "plain prompt only"

raw = resp.choices[0].message.content
print("Mode used :", mode)
print("Raw answer:", raw)

# Can Python read the answer as JSON?
try:
    data = json.loads(raw)
    print("JSON OK   :", data)
except json.JSONDecodeError:
    print("JSON FAILED - answer is not clean JSON (we will need to clean it)")
