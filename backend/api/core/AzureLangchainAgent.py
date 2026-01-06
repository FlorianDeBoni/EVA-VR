from typing import List, Dict, Generator, Any
from openai import AzureOpenAI
from decouple import config
import time

# -----------------------------
# Azure OpenAI configuration
# -----------------------------
AZURE_ENDPOINT = config("AZURE_ENDPOINT")
AZURE_API_VERSION = config("AZURE_API_VERSION")
AZURE_API_KEY = config("AZURE_OPENAI_KEY")

# IMPORTANT: this must be your Azure DEPLOYMENT NAME
GPT_COMPLETION_MODEL = config("GPT_COMPLETION_MODEL")

# -----------------------------
# Azure OpenAI client
# -----------------------------
client = AzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    api_version=AZURE_API_VERSION,
    api_key=AZURE_API_KEY,
    timeout=30,  # applied correctly at client level
)

# -----------------------------
# Streaming chat completion
# -----------------------------
def send_chat_completion_stream(
    history: List[Dict[str, Any]],
    model: str = GPT_COMPLETION_MODEL,
) -> Generator[str, None, None]:
    """
    Streams a chat completion from Azure OpenAI.

    Yields text chunks as they arrive, and finally yields [DONE].
    """

    response = client.chat.completions.create(
        model=model,
        messages=history,
        temperature=1.0,
        stream=True,
    )

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            for character in chunk.choices[0].delta.content:
                yield character
                time.sleep(0.001)

    yield "[DONE]"
