"""Check that the OpenRouter API key works by running inference on a free-tier model."""
import os
import sys

import requests
from dotenv import load_dotenv

MODEL = "baidu/ernie-5.5-flash-preview:free"
MESSAGE = "test"

load_dotenv()
r = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
    json={"model": MODEL, "messages": [{"role": "user", "content": MESSAGE}]},
    timeout=60,
)

if r.status_code != 200:
    print(f"[FAIL] {MODEL}: HTTP {r.status_code} - {r.text[:300]}")
    sys.exit(1)

print(f"[OK] {MODEL}: {r.json()['choices'][0]['message']['content']}")
