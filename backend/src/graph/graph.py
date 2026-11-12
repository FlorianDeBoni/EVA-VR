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
from backend.src.graph.subgraphs.spatial_design.graph import get_spatial_design_graph
from backend.src.settings.LogManager import LogManager


class MainGraph:
    """Entry point of the workshop conversation: a router in front of the subgraphs.

        graph = get_main_graph().graph
        graph.invoke({"messages": [...], "session_id": session_id, "information": info})

    Every subgraph uses the same `GraphState` as this graph, so the state goes in and
    out of a subgraph unchanged. The steps run in order:

    1. `gather_information` until the user validated the information,
    2. `concept_design` until the user validated the concept,
    3. `spatial_design` after that.

    `route` picks the subgraph of the current step (`current_step`). A step that gets
    validated ends its subgraph, and the next step starts in the very same turn
    (`next_step`), so the user is not left waiting. To add a step, add it to `Step` and
    `STEP_ROUTES`, and register its compiled graph in `subgraphs`.

    Pass `subgraphs` (name -> compiled graph) to replace the default ones (handy in tests).
    """

    DEFAULT_ROUTE = "gather_information"
    CONCEPT_DESIGN_ROUTE = "concept_design"
    SPATIAL_DESIGN_ROUTE = "spatial_design"
    # The subgraph that handles each step.
    STEP_ROUTES: ClassVar[dict[Step, str]] = {
        Step.GATHER_INFORMATION: DEFAULT_ROUTE,
        Step.CONCEPT_DESIGN: CONCEPT_DESIGN_ROUTE,
        Step.SPATIAL_DESIGN: SPATIAL_DESIGN_ROUTE,
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
                self.SPATIAL_DESIGN_ROUTE: get_spatial_design_graph().graph,
            }
        return self._subgraphs

    def route(self, state: GraphState) -> str:
        """Return the name of the subgraph that should handle this turn."""
        route = self.STEP_ROUTES[current_step(state)]
        self.logger.info("Routing to %s", route)
        return route

    def next_step(self, name: str):
        """The edge after subgraph `name`: on to the next step if this one is done, else END.

        A subgraph is done when the session moved to a later step during its turn.
        """

        def after(state: GraphState) -> str:
            target = self.STEP_ROUTES[current_step(state)]
            return END if target == name or target not in self.subgraphs else target

        return after

    def compile(self, checkpointer=None) -> CompiledStateGraph:
        """Build the graph: START -> router -> a subgraph -> END (or on to the next step)."""
        builder = StateGraph(GraphState)
        destinations = {**{name: name for name in self.subgraphs}, END: END}
        for name, subgraph in self.subgraphs.items():
            builder.add_node(name, subgraph)
            builder.add_conditional_edges(name, self.next_step(name), destinations)
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
