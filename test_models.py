import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()
models = client.models.list()
pro_models = [m.name for m in models if 'pro' in m.name and 'vision' not in m.name]
print("AVAILABLE PRO MODELS:")
for m in pro_models:
    print(m)
