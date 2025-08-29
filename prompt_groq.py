from groq import Groq
# main.py
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.getenv("QROQ_API_KEY")


"qwen/qwen3-32b"
"llama-3.3-70b-versatile"
"meta-llama/llama-guard-4-12b"
"openai/gpt-oss-120b"
"openai/gpt-oss-20b"
"openai/gpt-oss-120b"
"llama-3.1-8b-instant"



client = Groq(api_key=api_key)
completion = client.chat.completions.create(
    model="moonshotai/kimi-k2-instruct",
    messages=[
      {
        "role": "user",
        "content": "Qual é o raio da terra?"
      }
    ],
    temperature=0.6,
    max_completion_tokens=4096,
    top_p=0.95,
    #reasoning_effort="default",
    stream=True,
    stop=None
)

for chunk in completion:
    print(chunk.choices[0].delta.content or "", end="")

