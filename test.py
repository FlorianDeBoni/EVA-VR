API_KEY = ""

from google import genai
import base64

client = genai.Client(api_key=API_KEY)

print("List of models that support generateContent:\n")
for m in client.models.list():
    print(m.name, ":")
    for action in m.supported_actions:
        print(action)


response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="How does AI work?"
)
print(response.text)