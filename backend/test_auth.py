import os
from dotenv import load_dotenv

load_dotenv()

# Forcefully remove google application credentials from environment if they exist
# to force the usage of the raw API key instead of gcloud oauth.
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

import google.generativeai as genai

api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
print(f"Using API Key: {api_key[:5]}... (length: {len(api_key)})")

genai.configure(api_key=api_key)

try:
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content("What is 2+2? Only output the number.")
    print("Success! Output:", response.text)
except Exception as e:
    print("Error:", e)
