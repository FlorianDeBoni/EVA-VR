from functools import lru_cache
from typing import ClassVar

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.src.graph.state import GraphState
from backend.src.graph.steps import Step, current_step
from backend.src.graph.subgraphs.concept_design.graph import get_concept_design_graph
from backend.src.graph.subgraphs.information_gathering.graph import (
    get_information_gathering_graph,
)
from backend.src.settings.LogManager import LogManager


class MainGraph:
    """Entry point of the workshop conversation: a router in front of the subgraphs.

        graph = get_main_graph().graph
        graph.invoke({"messages": [...], "session_id": session_id, "information": info})

    Every subgraph uses the same `GraphState` as this graph, so the state goes in and
    out of a subgraph unchanged. The steps run in order:

    1. `gather_information` until the user validated the information,
    2. `concept_design` after that. It also starts in the very turn the information gets
       validated (`after_gather_information`), so the user is not left waiting.

    `route` picks the subgraph that handles the turn. To add a step, register its compiled
    graph in `subgraphs` and teach `route` when to choose it.

    Pass `subgraphs` (name -> compiled graph) to replace the default ones (handy in tests).
    """

    DEFAULT_ROUTE = "gather_information"
    CONCEPT_DESIGN_ROUTE = "concept_design"
    # The subgraph that handles each step.
    STEP_ROUTES: ClassVar[dict[Step, str]] = {
        Step.GATHER_INFORMATION: DEFAULT_ROUTE,
        Step.CONCEPT_DESIGN: CONCEPT_DESIGN_ROUTE,
    }

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
                self.CONCEPT_DESIGN_ROUTE: get_concept_design_graph().graph,
            }
        return self._subgraphs

    def route(self, state: GraphState) -> str:
        """Return the name of the subgraph that should handle this turn."""
        route = self.STEP_ROUTES[current_step(state)]
        self.logger.info("Routing to %s", route)
        return route

    def after_gather_information(self, state: GraphState) -> str:
        """Continue with the concept design in the same turn once the information is validated."""
        step = current_step(state)
        return self.STEP_ROUTES[step] if step > Step.GATHER_INFORMATION else END

    def compile(self, checkpointer=None) -> CompiledStateGraph:
        """Build the graph: START -> router -> a subgraph -> END (or on to the next step)."""
        builder = StateGraph(GraphState)
        for name, subgraph in self.subgraphs.items():
            builder.add_node(name, subgraph)
            if name == self.DEFAULT_ROUTE and self.CONCEPT_DESIGN_ROUTE in self.subgraphs:
                builder.add_conditional_edges(
                    name,
                    self.after_gather_information,
                    {self.CONCEPT_DESIGN_ROUTE: self.CONCEPT_DESIGN_ROUTE, END: END},
                )
            else:
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
