# NOTE: This is a temporary test file. Remove it before final submission.
from dotenv import load_dotenv
import os

MODEL = "nvidia/nemotron-3.5-lightning:free"
MESSAGE = "test"

load_dotenv()

from openai import OpenAI

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=os.getenv("OPENROUTER_API_KEY"),
)

# First API call with reasoning
response = client.chat.completions.create(
  model=MODEL,
  messages=[
          {
            "role": "user",
            "content": "test"
          }
        ],
  extra_body={"reasoning": {"enabled": False}}
)

# Extract the assistant message with reasoning_details
response = response.choices[0].message
print(response)

# # Preserve the assistant message with reasoning_details
# messages = [
#   {"role": "user", "content": "How many r's are in the word 'strawberry'?"},
#   {
#     "role": "assistant",
#     "content": response.content,
#     "reasoning_details": response.reasoning_details  # Pass back unmodified
#   },
#   {"role": "user", "content": "Are you sure? Think carefully."}
# ]

# # Second API call - model continues reasoning from where it left off
# response2 = client.chat.completions.create(
#   model="nvidia/nemotron-3.5-lightning:free",
#   messages=messages,
#   extra_body={"reasoning": {"enabled": True}}
# )

