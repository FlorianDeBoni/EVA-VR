import json
from dataclasses import asdict
from functools import lru_cache
from typing import ClassVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from backend.services.conceptDesignService import (
    ConceptDesignService,
    get_concept_design_service,
)
from backend.services.promptService import PromptService, get_prompt_service
from backend.src.graph.state import GraphState
from backend.src.graph.tools.concept_design.schemas import (
    ConceptDesign,
    ConceptImage,
    ReferenceImage,
)
from backend.src.graph.tools.concept_design.tool import generate_concept_image, validate_concept
from backend.src.graph.tools.search_web_images.tool import search_web_images
from backend.src.settings.envManager import EnvKeyName, EnvManager
from backend.src.settings.LogManager import LogManager

TOOLS = [search_web_images, generate_concept_image, validate_concept]


class ConceptDesignGraph:
    """Second conversational subgraph of the design workshop: the overall concept of the room.

    It finds 3 reference images on the web from the gathered information, asks the user
    which elements to keep, then generates a concept image and refines it with the user
    until they accept it (`search_web_images`, `generate_concept_image`,
    `validate_concept`). Only the overall design is discussed here; details come later.

        graph = get_concept_design_graph().graph
        graph.invoke({
            "messages": [...],
            "session_id": session_id,
            "information": information,
            "concept_design": concept_service.get_concept_design(session_id),
        })

    The model sees the images, not only text: before every model call, the reference images
    and the latest concept are read from the database and put in front of the conversation.
    The system prompt is `concept_design`, served by Langfuse (seeded with `task seed:prompts`).
    Pass `llm` to use another chat model (handy in tests); it must support `bind_tools` and
    image inputs.
    """

    PROMPT_NAME: ClassVar[str] = "concept_design"

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        prompt_service: PromptService | None = None,
        concept_service: ConceptDesignService | None = None,
    ) -> None:
        self._llm = llm
        self._bound_llm = None
        self._prompt_service = prompt_service
        self._concept_service = concept_service
        self._graph: CompiledStateGraph | None = None
        self.logger = LogManager.get_logger(__name__)

    @property
    def prompt_service(self) -> PromptService:
        if self._prompt_service is None:
            self._prompt_service = get_prompt_service()
        return self._prompt_service

    @property
    def concept_service(self) -> ConceptDesignService:
        if self._concept_service is None:
            self._concept_service = get_concept_design_service()
        return self._concept_service

    @property
    def llm(self) -> BaseChatModel:
        """The chat model with the tools bound (lazily created, cached)."""
        if self._bound_llm is None:
            llm = self._llm or ChatOpenAI(
                model=EnvManager.get_env_variable(EnvKeyName.KEY_OPENAI_CHAT_MODEL),
                api_key=EnvManager.get_env_variable(EnvKeyName.KEY_OPENAI_API_KEY),
            )
            # One tool call per model step: each generation builds on the previous one.
            self._bound_llm = llm.bind_tools(TOOLS, parallel_tool_calls=False)
        return self._bound_llm

    @staticmethod
    def status(concept: ConceptDesign) -> str:
        """What exists so far, in words, for the system prompt."""
        references = (
            f"{concept.reference_count} reference images found and shown to the user "
            f"(Reference 1 to {concept.reference_count})"
            if concept.reference_count
            else "none yet: search for them now"
        )
        concepts = (
            f"{concept.latest_version} version(s) generated, the latest is version "
            f"{concept.latest_version}"
            if concept.latest_version
            else "none yet"
        )
        return (
            f"- Reference images: {references}\n"
            f"- Generated concept images: {concepts}\n"
            f"- Concept validated by the user: {'yes' if concept.is_validated else 'no'}"
        )

    @staticmethod
    def images_message(
        references: list[ReferenceImage], latest: ConceptImage | None
    ) -> HumanMessage | None:
        """The images the user currently sees, as one message the model can look at."""

        def image(mime_type: str, image_b64: str) -> dict:
            return {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
            }

        content: list[dict] = []
        for reference in references:
            title = f" ({reference.title})" if reference.title else ""
            content.append({"type": "text", "text": f"Reference {reference.position}{title}:"})
            content.append(image(reference.mime_type, reference.image_b64))
        if latest is not None:
            content.append(
                {"type": "text", "text": f"Latest concept, version {latest.version} (generated):"}
            )
            content.append(image(latest.mime_type, latest.image_b64))
        if not content:
            return None
        intro = {
            "type": "text",
            "text": "Automatic context, not written by the user: the images the user sees now.",
        }
        return HumanMessage(content=[intro, *content])

    def agent_node(self, state: GraphState) -> dict:
        """Ask the model for the next message, given the information and the images."""
        session_id = state["session_id"]
        system = self.prompt_service.get(
            self.PROMPT_NAME,
            information=json.dumps(asdict(state["information"]), ensure_ascii=False, indent=2),
            status=self.status(state["concept_design"]),
        )
        context = self.images_message(
            self.concept_service.get_reference_images(session_id),
            self.concept_service.get_concept_image(session_id),
        )
        messages = [
            SystemMessage(content=system),
            *([context] if context else []),
            *state["messages"],
        ]
        return {"messages": [self.llm.invoke(messages)]}

    def compile(self, checkpointer=None) -> CompiledStateGraph:
        """Build the graph: agent <-> tools, ending when the agent stops calling tools."""
        builder = StateGraph(GraphState)
        builder.add_node("agent", self.agent_node)
        builder.add_node("tools", ToolNode(TOOLS))
        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
        builder.add_edge("tools", "agent")
        return builder.compile(checkpointer=checkpointer)

    @property
    def graph(self) -> CompiledStateGraph:
        """The compiled graph without checkpointer (lazily built, cached)."""
        if self._graph is None:
            self._graph = self.compile()
        return self._graph


@lru_cache(maxsize=1)
def get_concept_design_graph() -> ConceptDesignGraph:
    """Shared default graph instance."""
    return ConceptDesignGraph()
