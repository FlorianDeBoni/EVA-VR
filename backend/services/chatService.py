from functools import lru_cache
from uuid import UUID

from langchain_core.messages import AnyMessage
from langgraph.graph.state import CompiledStateGraph

from backend.services.conceptDesignService import ConceptDesignService, get_concept_design_service
from backend.services.databaseService import DatabaseService, get_database_service
from backend.src.graph.graph import get_main_graph
from backend.src.graph.state import GraphState
from backend.src.settings.LogManager import LogManager


class ChatService:
    """Runs the main graph for a conversation turn.

        service = get_chat_service()
        state = service.chat(session_id, messages)   # loads the session's information
        reply = state["messages"][-1].content

    `run` is the low-level entry point: it passes a complete `GraphState` to the main
    graph. `chat` builds that state from the session id and the conversation so far.
    The service keeps no history: the caller sends the messages back on every turn.
    """

    def __init__(
        self,
        graph: CompiledStateGraph | None = None,
        database_service: DatabaseService | None = None,
        concept_service: ConceptDesignService | None = None,
    ) -> None:
        self._graph = graph
        self._database_service = database_service
        self._concept_service = concept_service
        self.logger = LogManager.get_logger(__name__)

    @property
    def graph(self) -> CompiledStateGraph:
        if self._graph is None:
            self._graph = get_main_graph().graph
        return self._graph

    @property
    def database_service(self) -> DatabaseService:
        if self._database_service is None:
            self._database_service = get_database_service()
        return self._database_service

    @property
    def concept_service(self) -> ConceptDesignService:
        if self._concept_service is None:
            self._concept_service = get_concept_design_service()
        return self._concept_service

    def run(self, state: GraphState) -> GraphState:
        """Pass `state` to the main graph and return the resulting state."""
        return self.graph.invoke(state)

    def ensure_session(self, session_id: UUID | None) -> UUID:
        """Return `session_id` if that session exists, otherwise create it.

        With no id, a new session is created with a generated id. With an unknown id,
        the session is created under that same id.
        """
        if session_id is not None and self.database_service.session_exists(session_id):
            return session_id
        created = self.database_service.create_session(session_id)
        self.logger.info("Created session %s", created)
        return created

    def chat(self, session_id: UUID, messages: list[AnyMessage]) -> GraphState:
        """Run one turn of the conversation of a session.

        Args:
            session_id: The session whose gathered information is read and updated.
            messages: The whole conversation so far, ending with the user's message.

        Returns:
            The final state: its last message is the assistant's reply and its
            `information` and `concept_design` are up to date with the database.

        Raises:
            SessionNotFoundError: If no session has this id.
        """
        state: GraphState = {
            "messages": messages,
            "session_id": session_id,
            "information": self.database_service.get_information(session_id),
            "concept_design": self.concept_service.get_concept_design(session_id),
        }
        self.logger.info("Chat turn for session %s (%d messages)", session_id, len(messages))
        return self.run(state)


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    """Shared default service instance."""
    return ChatService()
