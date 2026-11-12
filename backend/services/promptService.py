from functools import lru_cache
from pathlib import Path

from langfuse import Langfuse
from langfuse.api import NotFoundError

from backend.infra.langfuseClient import LangfuseClient
from backend.services.errors import PromptNotFoundError
from backend.src.settings.envManager import EnvKeyName, EnvManager
from backend.src.settings.LogManager import LogManager


class PromptService:
    """Serves prompts from Langfuse.

        text = get_prompt_service().get("information_gathering", information="...")

    Prompts are tuned in Langfuse and read at runtime under the configured label
    (LANGFUSE_PROMPT_LABEL). They are first loaded from markdown files with `seed()`
    (`task seed:prompts`, files in infrastructure/langfuse/prompts).
    Variables use Langfuse's `{{name}}` syntax.
    """

    def __init__(self, client: Langfuse | None = None, label: str | None = None) -> None:
        self._client = client
        self._label = label
        self.logger = LogManager.get_logger(__name__)

    @property
    def client(self) -> Langfuse:
        if self._client is None:
            self._client = LangfuseClient.from_env().get_client()
        return self._client

    @property
    def label(self) -> str:
        return self._label or EnvManager.get_env_variable(EnvKeyName.KEY_LANGFUSE_PROMPT_LABEL)

    def get(self, name: str, **variables: str) -> str:
        """Return the prompt `name` with its `{{variables}}` filled in.

        Raises:
            PromptNotFoundError: If Langfuse has no such prompt under the label.
        """
        try:
            prompt = self.client.get_prompt(name, label=self.label, type="text")
        except NotFoundError as exc:
            raise PromptNotFoundError(
                f"prompt '{name}' (label '{self.label}') not found in Langfuse: "
                "run `task seed:prompts`"
            ) from exc
        return prompt.compile(**variables)

    def seed(self, prompts_dir: Path) -> dict[str, str]:
        """Publish every *.md file of `prompts_dir` to Langfuse under the configured label.

        The prompt name is the file name without extension. A new version is created
        only when the content differs from the current one.

        Returns:
            Prompt name -> "created", "updated" or "unchanged".
        """
        result: dict[str, str] = {}
        for path in sorted(prompts_dir.glob("*.md")):
            name, content = path.stem, path.read_text(encoding="utf-8")
            try:
                current = self.client.get_prompt(
                    name, label=self.label, type="text", cache_ttl_seconds=0
                )
            except NotFoundError:
                current = None

            if current is not None and current.prompt == content:
                result[name] = "unchanged"
                continue

            self.client.create_prompt(name=name, prompt=content, labels=[self.label], type="text")
            result[name] = "created" if current is None else "updated"
            self.logger.info("Prompt %s %s in Langfuse", name, result[name])
        self.client.flush()
        return result


@lru_cache(maxsize=1)
def get_prompt_service() -> PromptService:
    """Shared default service instance."""
    return PromptService()
