"""Publish a folder of markdown prompts to Langfuse: `task seed:prompts`.

Usage: python -m backend.scripts.seed_prompts <prompts_dir>
"""

import sys
from pathlib import Path

from backend.services.promptService import get_prompt_service


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    prompts_dir = Path(argv[0])
    if not prompts_dir.is_dir():
        print(f"not a directory: {prompts_dir}")
        return 1
    for name, status in get_prompt_service().seed(prompts_dir).items():
        print(f"{name}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
