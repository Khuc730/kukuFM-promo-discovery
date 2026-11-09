
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv(override=True)

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)

print("Testing Groq inference...")

try:
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": "You are an expert microdrama promotional editor."
            },
            {
                "role": "user",
                "content": (
                    "In two sentences, explain what makes a good "
                    "20-60 second microdrama advertisement."
                )
            }
        ],
        temperature=0.2,
        max_completion_tokens=200
    )

    print("\nSUCCESS!")
    print(response.choices[0].message.content)

    print("\nToken usage:", response.usage)

except Exception as error:
    print("\nGROQ INFERENCE FAILED")
    print(type(error).__name__, error)
