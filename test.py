
from google import genai

client = genai.Client(api_key=API_KEY)

print("List of models that support generateContent:\n")
# for m in client.models.list():
#     print(m.name, ":")
#     for action in m.supported_actions:
#         print(action)


prompt = (
    "Create a picture of my cat eating a nano-banana in a "
    "fancy restaurant under the Gemini constellation",
)

response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[prompt],
)

for part in response.parts:
    if part.text is not None:
        print(part.text)
    elif part.inline_data is not None:
        image = part.as_image()
        image.save("generated_image.png")