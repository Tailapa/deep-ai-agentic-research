import re
import asyncio
from datetime import datetime

from agents import Runner, trace, gen_trace_id

from planner_agent import planner_agent, WebSearchItem, WebSearchPlan
from search_agent import search_agent, SearchSummary
from styled_writer_agent import styled_writer_agent
from writer_agent import ReportData
from email_agent import email_agent
from doc_export_agent import doc_export_agent
import database


class ResearchManager:

    async def run(self, query: str, recipients: str = ""):
        """Run the full deep-research pipeline, yielding status updates then the final report."""
        trace_id = gen_trace_id()
        with trace("Research trace", trace_id=trace_id):
            print(f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}")
            yield f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}"

            search_plan = await self.plan_searches(query)
            yield f"Planned {len(search_plan.searches)} searches — running in parallel..."

            search_results = await self.perform_searches(search_plan)
            yield f"Got {len(search_results)} search results — writing report..."

            report = await self.write_report(query, search_results)
            yield "Report written — saving to database..."

            all_sources = list(dict.fromkeys(url for r in search_results for url in r.sources))
            report_id = await database.save_report(
                query=query,
                summary=report.short_summary,
                markdown_report=report.markdown_report,
                follow_up_questions=report.follow_up_questions,
                sources=all_sources,
            )
            yield f"Saved as report #{report_id} — exporting to DOCX..."

            docx_path = await self.export_docx(report, query)
            if docx_path:
                await database.update_docx_path(report_id, docx_path)
                yield f"DOCX saved to {docx_path} — sending email..."
            else:
                yield "DOCX export failed (continuing) — sending email..."

            email_ok = await self.send_email(report, recipients)
            yield "Email sent — research complete." if email_ok else "Email failed (network error) — research complete."
            yield report.markdown_report

    # ------------------------------------------------------------------
    # Individual pipeline steps
    # ------------------------------------------------------------------

    async def plan_searches(self, query: str) -> WebSearchPlan:
        print("Planning searches...")
        result = await Runner.run(planner_agent, f"Query: {query}")
        print(f"Will perform {len(result.final_output.searches)} searches")
        return result.final_output_as(WebSearchPlan)

    async def perform_searches(self, search_plan: WebSearchPlan) -> list[SearchSummary]:
        print("Searching...")
        tasks = [asyncio.create_task(self._search(item)) for item in search_plan.searches]
        results: list[SearchSummary] = []
        completed = 0
        for task in asyncio.as_completed(tasks):
            result = await task
            if result is not None:
                results.append(result)
            completed += 1
            print(f"Searching... {completed}/{len(tasks)} done")
        print("All searches finished")
        return results

    async def _search(self, item: WebSearchItem) -> SearchSummary | None:
        input_text = f"Search term: {item.query}\nReason for searching: {item.reason}"
        try:
            result = await Runner.run(search_agent, input_text)
            return result.final_output_as(SearchSummary)
        except Exception as e:
            print(f"Search failed for '{item.query}': {e}")
            return None

    async def write_report(self, query: str, search_results: list[SearchSummary]) -> ReportData:
        print("Writing report...")
        formatted: list[str] = []
        for i, r in enumerate(search_results, 1):
            sources_str = "\n".join(f"  {j}. {url}" for j, url in enumerate(r.sources, 1))
            formatted.append(
                f"--- Search Result {i} ---\n{r.summary}\n\nSources found:\n{sources_str}"
            )
        input_text = f"Original query: {query}\n\n" + "\n\n".join(formatted)
        result = await Runner.run(styled_writer_agent, input_text)
        print("Report written")
        return result.final_output_as(ReportData)

    async def export_docx(self, report: ReportData, query: str) -> str:
        print("Exporting to DOCX...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = re.sub(r"[^\w\s]", "", query)[:30].strip().replace(" ", "_")
        filename = f"report_{timestamp}_{safe_query}"
        input_text = f"Filename: {filename}\n\n{report.markdown_report}"
        try:
            result = await Runner.run(doc_export_agent, input_text)
            path = str(result.final_output)
            print(f"DOCX saved: {path}")
            return path
        except Exception as e:
            print(f"DOCX export failed: {e}")
            return ""

    async def send_email(self, report: ReportData, recipients: str = "") -> bool:
        print("Sending email...")
        input_text = report.markdown_report
        if recipients.strip():
            input_text = f"Send to: {recipients}\n\n{report.markdown_report}"
        try:
            await Runner.run(email_agent, input_text)
            print("Email sent")
            return True
        except Exception as e:
            print(f"Email failed: {e}")
            return False
