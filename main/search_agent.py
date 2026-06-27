from agents import Agent, ModelSettings, function_tool
from pydantic import BaseModel, Field
from tavily import TavilyClient
from typing import Dict
import os


class SearchSummary(BaseModel):
    summary: str = Field(
        description="2-3 paragraph summary of the search results, under 300 words. Capture essence only."
    )
    sources: list[str] = Field(
        description="List of every URL from the search results that was relevant to the summary."
    )


INSTRUCTIONS = (
    "You are a research assistant. Given a search term, you search the web for that term and "
    "produce a concise summary of the results. The summary must be 2-3 paragraphs and less than 300 "
    "words. Capture the main points. Write succinctly — no need for complete sentences or polished "
    "grammar. This will be consumed by someone synthesizing a report, so capture the essence and "
    "ignore fluff. Do not include any additional commentary other than the summary itself. "
    "Also collect every source URL from the search results that was relevant to your summary."
)


@function_tool
def tavily_search_tool(query: str) -> Dict[str, str]:
    """Search the live web for up-to-date information, news, data, and facts using Tavily.
    Always pass a clear, specific search string here."""
    tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY_1"))
    try:
        response = tavily.search(query=query, max_results=10)
        results = []
        for item in response.get("results", []):
            results.append(f"Title: {item['title']}\nURL: {item['url']}\nSnippet: {item['content']}\n---")
        return {"search_results": "\n".join(results) if results else "No results found."}
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


search_agent = Agent(
    name="Search agent",
    instructions=INSTRUCTIONS,
    tools=[tavily_search_tool],
    model="gpt-4o-mini",
    model_settings=ModelSettings(tool_choice="required"),
    output_type=SearchSummary,
)
