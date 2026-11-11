import base64

from backend.src.graph.tools.generate_image import tool as tool_module
from backend.src.graph.tools.generate_image.schemas import GeneratedImage
from backend.src.graph.tools.generate_image.tool import generate_image


def test_tool_schema_exposes_only_prompt():
    props = generate_image.args_schema.model_json_schema()["properties"]
    assert set(props) == {"prompt"}


def test_tool_returns_image_as_base64(monkeypatch):
    seen = {}

    class FakeGenerator:
        def generate(self, prompt):
            seen["prompt"] = prompt
            return GeneratedImage(b"\x89PNG fake", "image/png")

    monkeypatch.setattr(tool_module, "get_image_generator_service", lambda: FakeGenerator())

    out = generate_image.invoke({"prompt": "a pavilion"})

    assert seen["prompt"] == "a pavilion"
    assert base64.b64decode(out) == b"\x89PNG fake"
