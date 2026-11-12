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
from backend.src.graph.steps import Step
from backend.src.graph.tools.concept_design.schemas import ConceptImage
from backend.src.graph.tools.detailed_design.schemas import DetailedDesign
from backend.src.graph.tools.detailed_design.tool import (
    update_detailed_design,
    validate_detailed_design,
)
from backend.src.graph.tools.generate_image.tool import generate_image
from backend.src.graph.tools.spatial_design.schemas import SpatialDesign
from backend.src.settings.envManager import EnvKeyName, EnvManager
from backend.src.settings.LogManager import LogManager

TOOLS = [update_detailed_design, generate_image, validate_detailed_design]


class DetailedDesignGraph:
    """Last conversational subgraph of the design workshop: the details of the room.

    It starts from the picture the user validated in the spatial design step and keeps its
    layout: only minor details change. It proposes a first draft of the details the creative
    task needs (furniture above all, then shapes, materials, colors, lighting, accessories),
    refines it with the user by asking questions (`update_detailed_design` saves each change),
    then draws the result: `generate_image` makes a final version of the picture, the user
    refines it, and `validate_detailed_design` stores the details with the picture they
    accepted. That picture is the final result of the workshop.

        graph = get_detailed_design_graph().graph
        graph.invoke({
            "messages": [...],
            "session_id": session_id,
            "information": information,
            "concept_design": concept_design,
            "spatial_design": spatial_design,
            "detailed_design": detailed_service.get_detailed_design(session_id),
        })

    The model sees the images: before every model call, the validated spatial picture and the
    latest picture of this step are read from the database and put in front of the
    conversation. The system prompt is `detailed_design`, served by Langfuse (seeded with
    `task seed:prompts`).
    Pass `llm` to use another chat model (handy in tests); it must support `bind_tools` and
    image inputs.
    """

    PROMPT_NAME: ClassVar[str] = "detailed_design"

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
            # One tool call per model step: each update rewrites the whole list of details.
            self._bound_llm = llm.bind_tools(TOOLS, parallel_tool_calls=False)
        return self._bound_llm

    @staticmethod
    def spaces_json(design: SpatialDesign) -> str:
        """The validated spaces and relationships as JSON for the system prompt."""
        data = asdict(design)
        del data["is_validated"], data["latest_image_version"]
        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def design_json(design: DetailedDesign) -> str:
        """The draft details as JSON for the system prompt (the validation is in the status)."""
        return json.dumps({"details": asdict(design)["details"]}, ensure_ascii=False, indent=2)

    @staticmethod
    def status(design: DetailedDesign) -> str:
        """Where the draft stands, in words, for the system prompt."""
        draft = (
            f"{len(design.details)} detail(s) saved"
            if design.details
            else "none yet: record a first draft now"
        )
        pictures = (
            f"the latest is version {design.latest_image_version}"
            if design.latest_image_version
            else "none yet"
        )
        return (
            f"- Draft: {draft}\n"
            f"- Pictures of the details generated: {pictures}\n"
            f"- Validated by the user: {'yes' if design.is_validated else 'no'}"
        )

    @staticmethod
    def images_message(spatial_b64: str | None, latest: ConceptImage | None) -> HumanMessage | None:
        """The validated spatial picture and the latest picture of this step, for the model."""

        def image(mime_type: str, image_b64: str) -> dict:
            return {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
            }

        content: list[dict] = []
        if spatial_b64 is not None:
            content.append(
                {
                    "type": "text",
                    "text": "The picture of the spatial organization the user validated in the "
                    "previous step:",
                }
            )
            content.append(image("image/png", spatial_b64))
        if latest is not None:
            content.append(
                {
                    "type": "text",
                    "text": "The latest picture with the details, version "
                    f"{latest.version} (generated by you):",
                }
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
        """Ask the model for the next message, given the information, the draft and the images."""
        session_id = state["session_id"]
        system = self.prompt_service.get(
            self.PROMPT_NAME,
            information=json.dumps(asdict(state["information"]), ensure_ascii=False, indent=2),
            spatial_design=self.spaces_json(state["spatial_design"]),
            detailed_design=self.design_json(state["detailed_design"]),
            status=self.status(state["detailed_design"]),
        )
        context = self.images_message(
            self.concept_service.get_validated_image(session_id, step=Step.SPATIAL_DESIGN),
            self.concept_service.get_concept_image(session_id, step=Step.DETAILED_DESIGN),
        )
        messages = [
            SystemMessage(content=system),
            *([context] if context else []),
            *state["messages"],
        ]
        return {"messages": [self.llm.invoke(messages)]}

    def compile(self, checkpointer=None) -> CompiledStateGraph:
        """Build the graph: agent <-> tools, ending when the agent stops calling tools.

        It is the last step, so the agent also speaks after `validate_detailed_design`.
        """
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
def get_detailed_design_graph() -> DetailedDesignGraph:
    """Shared default graph instance."""
    return DetailedDesignGraph()
