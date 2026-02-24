import chainlit as cl
from src.graph import build_graph
from src.state import ScientificDiscoveryState
import traceback

@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content="# Scientific Discovery Engine\nWelcome! Please enter a research topic to begin.").send()

@cl.on_message
async def on_message(message: cl.Message):
    query = message.content

    await cl.Message(content=f"Starting research on: **{query}**").send()

    initial_state = ScientificDiscoveryState(
        query=query,
        scout_queries={},
        papers=[],
        report="",
        logs=[]
    )

    app = build_graph()

    final_report = "No report generated."

    try:
        # We run the synchronous stream.
        # Since Chainlit runs in an async loop, this will block the loop.
        # For a single user, this is fine.
        stream = app.stream(initial_state, stream_mode="updates")

        for event in stream:
            for node, values in event.items():

                # Supervisor
                if node == "supervisor":
                    queries = values.get("scout_queries", {})
                    content = "Generated search queries:\n"
                    for source, q in queries.items():
                        content += f"- **{source.capitalize()}**: {q}\n"

                    async with cl.Step(name="Supervisor Agent") as step:
                        step.output = content

                # Scouts
                elif node == "scouts":
                    papers = values.get("papers", [])

                    content = f"Found **{len(papers)}** papers across sources.\n"
                    sources = {}
                    for p in papers:
                        # p is a Paper object
                        sources[p.source] = sources.get(p.source, 0) + 1

                    for s, count in sources.items():
                        content += f"- {s}: {count}\n"

                    async with cl.Step(name="Scout Agents") as step:
                        step.output = content

                # Fetcher
                elif node == "fetcher":
                    papers = values.get("papers", [])
                    fetched_count = sum(1 for p in papers if p.full_text)
                    async with cl.Step(name="Fetcher Agent") as step:
                        step.output = f"Successfully fetched full text for **{fetched_count}/{len(papers)}** papers."

                # Analyst
                elif node == "analyst":
                    papers = values.get("papers", [])
                    # Count how many have relevance score > 0 or key findings
                    analyzed_count = sum(1 for p in papers if p.relevance_score > 0 or p.key_findings)

                    content = f"Analyzed **{analyzed_count}** papers.\n"
                    # Show top relevant papers
                    top_papers = sorted(papers, key=lambda p: p.relevance_score, reverse=True)[:3]
                    if top_papers:
                        content += "\n**Top Relevant Papers:**\n"
                        for p in top_papers:
                            content += f"- {p.title} (Score: {p.relevance_score})\n"

                    async with cl.Step(name="Analyst Agent") as step:
                        step.output = content

                # Writer
                elif node == "writer":
                    report = values.get("report", "")
                    final_report = report
                    async with cl.Step(name="Writer Agent") as step:
                        step.output = "Report generation complete."

        # Send the final report
        await cl.Message(content=final_report).send()

    except Exception as e:
        error_msg = f"An error occurred during execution: {str(e)}"
        await cl.Message(content=error_msg).send()
        print(error_msg)
        traceback.print_exc()
