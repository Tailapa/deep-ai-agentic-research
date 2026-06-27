from dotenv import load_dotenv
load_dotenv(override=True)  # must run before any module reads os.environ at import time

import gradio as gr
from research_manager import ResearchManager
import database
database.init_db()

_DEFAULT_RECIPIENTS = "shashankvshourya@gmail.com, sstudios147@gmail.com"


# ------------------------------------------------------------------
# Research tab handlers
# ------------------------------------------------------------------

async def run_research(query: str, recipients: str):
    async for chunk in ResearchManager().run(query, recipients):
        yield chunk


# ------------------------------------------------------------------
# History tab handlers
# ------------------------------------------------------------------

async def load_history(keyword: str):
    if keyword and keyword.strip():
        rows = await database.search_reports(keyword.strip())
    else:
        rows = await database.get_all_reports()
    return [
        [r["id"], r["created_at"], r["query"][:80], (r["short_summary"] or "")[:120]]
        for r in rows
    ]


async def load_report_by_id(report_id):
    if report_id is None or str(report_id).strip() == "":
        return "Enter a report ID and click Load."
    try:
        rid = int(report_id)
    except ValueError:
        return "Invalid ID — must be a number."
    report = await database.get_report(rid)
    if report is None:
        return f"No report found with ID {rid}."
    follow_up_md = "\n".join(f"- {q}" for q in report["follow_up_questions"]) if report["follow_up_questions"] else "_none_"
    docx_line = f"\n\n**DOCX:** `{report['docx_path']}`" if report.get("docx_path") else ""
    header = (
        f"## Report #{rid}\n"
        f"**Query:** {report['query']}  \n"
        f"**Date:** {report['created_at']}  \n"
        f"**Summary:** {report['short_summary']}{docx_line}\n\n"
        f"**Sources:** {len(report['sources'])} collected\n\n"
        f"**Follow-up questions:**\n{follow_up_md}\n\n---\n\n"
    )
    return header + report["markdown_report"]


# ------------------------------------------------------------------
# UI
# ------------------------------------------------------------------

with gr.Blocks(theme=gr.themes.Default(primary_hue="sky"), title="Deep Research") as ui:
    gr.Markdown("# Deep Research")

    with gr.Tabs():

        # ── Research tab ──────────────────────────────────────────
        with gr.Tab("Research"):
            query_box = gr.Textbox(
                label="What topic would you like to research?",
                placeholder="e.g. India's semiconductor policy 2024-2030",
                lines=2,
            )
            recipients_box = gr.Textbox(
                label="Email recipients (comma-separated)",
                value=_DEFAULT_RECIPIENTS,
                placeholder="email1@example.com, email2@example.com",
            )
            run_btn = gr.Button("Run Research", variant="primary")
            report_out = gr.Markdown(label="Report")

            run_btn.click(fn=run_research, inputs=[query_box, recipients_box], outputs=report_out)
            query_box.submit(fn=run_research, inputs=[query_box, recipients_box], outputs=report_out)

        # ── History tab ───────────────────────────────────────────
        with gr.Tab("History"):
            gr.Markdown("### Past Reports")
            gr.Markdown(
                "Search uses SQLite FTS5 full-text search across query, summary, and report body. "
                "Leave blank to list all reports."
            )

            with gr.Row():
                search_box = gr.Textbox(
                    label="Search keyword",
                    placeholder="e.g. semiconductor  OR  India defence",
                    scale=4,
                )
                search_btn = gr.Button("Search", scale=1)

            history_table = gr.Dataframe(
                headers=["ID", "Date (UTC)", "Query", "Summary"],
                datatype=("number", "str", "str", "str"),
                label="Reports",
                interactive=False,
                wrap=True,
            )

            with gr.Row():
                id_input = gr.Number(label="Report ID to load", precision=0, minimum=1)
                load_btn = gr.Button("Load Report")

            loaded_report = gr.Markdown(label="Loaded Report", value="Select a report ID above and click Load.")

            # Wire up
            search_btn.click(fn=load_history, inputs=search_box, outputs=history_table)
            search_box.submit(fn=load_history, inputs=search_box, outputs=history_table)
            load_btn.click(fn=load_report_by_id, inputs=id_input, outputs=loaded_report)

            # Populate table on tab load
            ui.load(fn=load_history, inputs=search_box, outputs=history_table)


ui.launch(inbrowser=True)
