GEMINI_IMAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": (
            "Generate or refine an AI image using Gemini. "
            "If needs_image is true, the system will provide the previous image "
            "for refinement instead of starting from scratch."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "A concrete, visual description of the image"
                },
                "needs_image": {
                    "type": "boolean",
                    "description": (
                        "Set to true ONLY if the request is a refinement of the "
                        "previously generated image."
                    )
                }
            },
            "required": ["prompt"],
        },
    },
}


REFERENCE_IMAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_reference_images",
        "description": (
            "Fetch multiple candidate reference images for a real-world concept. "
            "Returns a LIST of plausible images from Wikipedia or Wikimedia Commons. "
            "You MUST choose exactly ONE image that best represents the concept visually, "
            "or explicitly reject all candidates if none are suitable."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A concise, concrete, real-world description suitable for image search. "
                        "Avoid abstract language."
                    )
                }
            },
            "required": ["query"]
        }
    }
}