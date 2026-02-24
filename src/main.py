import argparse
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.graph import build_graph
from src.state import ScientificDiscoveryState

def main():
    parser = argparse.ArgumentParser(description="Scientific Discovery Engine")
    parser.add_argument("query", help="The research query")
    args = parser.parse_args()

    # Ensure outputs dir exists
    os.makedirs("outputs", exist_ok=True)

    print(f"Starting research on: {args.query}")

    app = build_graph()

    initial_state = ScientificDiscoveryState(
        query=args.query,
        scout_queries={},
        papers=[],
        report="",
        logs=[]
    )

    try:
        # LangGraph stream returns state updates as they happen
        # We use stream_mode="values" to get the full state after each step
        final_state = initial_state
        for state in app.stream(initial_state, stream_mode="values"):
            final_state = state
            # We don't have the node name directly here but we can stream values
            # Alternatively we could have kept the default mode but used app.get_state()
            print("Step finished...")

        report = final_state.get("report", "No report generated.")
        print("\n--- Final Report ---\n")
        print(report[:500] + "..." if len(report) > 500 else report)

        output_path = os.path.join("outputs", "report.md")
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(report)

        print(f"\nReport saved to {output_path}")

        # Save logs too
        logs_path = os.path.join("outputs", "logs.txt")
        with open(logs_path, "w", encoding='utf-8') as f:
            for log in final_state.get("logs", []):
                f.write(str(log) + "\n")
        print(f"Logs saved to {logs_path}")

    except Exception as e:
        print(f"Error executing graph: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
