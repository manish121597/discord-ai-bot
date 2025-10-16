import google.generativeai as genai
import os

# Make sure your GEMINI_API_KEY is set in environment or .env
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

model = genai.GenerativeModel("models/gemini-2.5-flash")
resp = model.generate_content("Hi Gemini, testing connection from my Discord bot.")
print(resp.text)
