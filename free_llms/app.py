
import os
import random
import json
from openai import OpenAI

api_keys = json.load(open('api_keys.json', 'r'))

def create_llm():
    # random sample a api key
    i = random.randint(0, len(api_keys) - 1)
    api_key = api_keys[i]
    client = OpenAI(base_url=api_key['base_url'], api_key=api_key['key'])
    return client


if __name__ == '__main__':
    client = create_llm()
    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[
            {"role": "user", "content": "Translate the following English text to French: 'Hello, how are you?'"}
        ],
    )
    print(response.choices[0].message.content)