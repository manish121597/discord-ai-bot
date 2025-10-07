import google.generativeai as genai
genai.configure(api_key="AIzaSyAn6_1YND8XuElEJnwAm1EAKgEUTkR6DE4")
print([m.name for m in genai.list_models()])
