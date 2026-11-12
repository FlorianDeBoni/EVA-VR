from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.src.graph.state import GraphState
from backend.src.graph.subgraphs.information_gathering.graph import (
    get_information_gathering_graph,
)
from backend.src.settings.LogManager import LogManager


class MainGraph:
    """Entry point of the workshop conversation: a router in front of the subgraphs.

        graph = get_main_graph().graph
        graph.invoke({"messages": [...], "session_id": session_id, "information": info})

    Every subgraph uses the same `GraphState` as this graph, so the state goes in and
    out of a subgraph unchanged. `route` picks the subgraph that handles the turn;
    today there is only `gather_information`. To add a step, register its compiled
    graph in `subgraphs` and teach `route` when to choose it.

    Pass `subgraphs` (name -> compiled graph) to replace the default ones (handy in tests).
    """

    DEFAULT_ROUTE = "gather_information"

    def __init__(self, subgraphs: dict[str, CompiledStateGraph] | None = None) -> None:
        self._subgraphs = subgraphs
        self._graph: CompiledStateGraph | None = None
        self.logger = LogManager.get_logger(__name__)

    @property
    def subgraphs(self) -> dict[str, CompiledStateGraph]:
        """The routable subgraphs by name (lazily built, cached)."""
        if self._subgraphs is None:
            self._subgraphs = {
                self.DEFAULT_ROUTE: get_information_gathering_graph().graph,
            }
        return self._subgraphs

    def route(self, state: GraphState) -> str:
        """Return the name of the subgraph that should handle this turn."""
        self.logger.info("Routing to %s", self.DEFAULT_ROUTE)
        return self.DEFAULT_ROUTE

    def compile(self, checkpointer=None) -> CompiledStateGraph:
        """Build the graph: START -> router -> one subgraph -> END."""
        builder = StateGraph(GraphState)
        for name, subgraph in self.subgraphs.items():
            builder.add_node(name, subgraph)
            builder.add_edge(name, END)
        builder.add_conditional_edges(START, self.route, {name: name for name in self.subgraphs})
        return builder.compile(checkpointer=checkpointer)

    @property
    def graph(self) -> CompiledStateGraph:
        """The compiled graph without checkpointer (lazily built, cached)."""
        if self._graph is None:
            self._graph = self.compile()
        return self._graph


@lru_cache(maxsize=1)
def get_main_graph() -> MainGraph:
    """Shared default main graph instance."""
    return MainGraph()
