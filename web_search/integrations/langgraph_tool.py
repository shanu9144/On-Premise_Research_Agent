from ..core.orchestrator import intelligent_web_search

# Verbatim wording recommended by Exa's build-with-exa skill for agent search tools.
OBJECTIVE_DESCRIPTION = ("Goal for this search turn; say which documents should rank first, which should be "
                         "excluded, and what specific facts or figures to pull from them.")
QUERY_DESCRIPTION = "Natural-language web search query."


def web_search(query: str, objective: str, max_results: int = 5) -> dict:
    """Search the web for current information and return cited sources."""
    return intelligent_web_search(query, {"objective": objective, "max_results": max_results})


def as_langchain_tool():
    """Wrap web_search as a LangChain/LangGraph tool (requires langchain-core)."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class WebSearchArgs(BaseModel):
        query: str = Field(description=QUERY_DESCRIPTION)
        objective: str = Field(description=OBJECTIVE_DESCRIPTION)
        max_results: int = Field(default=5, ge=1, le=10)

    return StructuredTool.from_function(web_search, name="intelligent_web_search", args_schema=WebSearchArgs,
                                        description=web_search.__doc__)
