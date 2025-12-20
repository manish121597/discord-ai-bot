import google.generativeai as genai
import os

# Load your Gemini API key from environment variable
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ GEMINI_API_KEY not set.")
else:
    genai.configure(api_key=api_key)

    print("🔍 Fetching available Gemini models...\n")
    models = genai.list_models()

    for m in models:
        print(f"• {m.name} | Supported methods: {m.supported_generation_methods}")
