import json
from dataclasses import asdict
from functools import lru_cache
from typing import ClassVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from backend.services.promptService import PromptService, get_prompt_service
from backend.src.graph.state import GraphState
from backend.src.graph.tools.gather_information.tool import (
    update_information,
    validate_information,
)
from backend.src.settings.envManager import EnvKeyName, EnvManager
from backend.src.settings.LogManager import LogManager


class InformationGatheringGraph:
    """First conversational subgraph of the design workshop.

    It chats with the user until the session's InformationToGather is complete, saves
    it step by step with `update_information`, asks for confirmation, then flags it
    with `validate_information`.

        graph = get_information_gathering_graph().graph
        graph.invoke({
            "messages": [("user", "Hi")],
            "session_id": session_id,
            "information": database_service.get_information(session_id),
        })

    The system prompt is `information_gathering`, served by Langfuse
    (seeded with `task seed:prompts`).
    Pass `llm` to use another chat model (handy in tests); it must support `bind_tools`.
    """

    PROMPT_NAME: ClassVar[str] = "information_gathering"

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        prompt_service: PromptService | None = None,
    ) -> None:
        self._llm = llm
        self._bound_llm = None
        self._prompt_service = prompt_service
        self._graph: CompiledStateGraph | None = None
        self.logger = LogManager.get_logger(__name__)

    @property
    def prompt_service(self) -> PromptService:
        if self._prompt_service is None:
            self._prompt_service = get_prompt_service()
        return self._prompt_service

    @property
    def llm(self) -> BaseChatModel:
        """The chat model with the two tools bound (lazily created, cached)."""
        if self._bound_llm is None:
            llm = self._llm or ChatOpenAI(
                model=EnvManager.get_env_variable(EnvKeyName.KEY_OPENAI_CHAT_MODEL),
                api_key=EnvManager.get_env_variable(EnvKeyName.KEY_OPENAI_API_KEY),
            )
            # One tool call per model step: parallel calls would each rewrite the whole row
            # from the same stale state (lost update) and conflict on the `information` key.
            self._bound_llm = llm.bind_tools(
                [update_information, validate_information], parallel_tool_calls=False
            )
        return self._bound_llm

    def agent_node(self, state: GraphState) -> dict:
        """Ask the model for the next message, given the current information."""
        system = self.prompt_service.get(
            self.PROMPT_NAME,
            information=json.dumps(asdict(state["information"]), ensure_ascii=False, indent=2),
        )
        response = self.llm.invoke([SystemMessage(content=system), *state["messages"]])
        return {"messages": [response]}

    @staticmethod
    def after_tools(state: GraphState) -> str:
        """Back to the agent, unless the information was just validated: the step is over."""
        return END if state["information"].is_validated else "agent"

    def compile(self, checkpointer=None) -> CompiledStateGraph:
        """Build the graph: agent <-> tools.

        It ends when the agent stops calling tools, or right after `validate_information`
        succeeds: the main graph then moves on to the next step, which speaks next.
        """
        builder = StateGraph(GraphState)
        builder.add_node("agent", self.agent_node)
        builder.add_node("tools", ToolNode([update_information, validate_information]))
        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
        builder.add_conditional_edges("tools", self.after_tools, {"agent": "agent", END: END})
        return builder.compile(checkpointer=checkpointer)

    @property
    def graph(self) -> CompiledStateGraph:
        """The compiled graph without checkpointer (lazily built, cached)."""
        if self._graph is None:
            self._graph = self.compile()
        return self._graph


@lru_cache(maxsize=1)
def get_information_gathering_graph() -> InformationGatheringGraph:
    """Shared default graph instance."""
    return InformationGatheringGraph()
