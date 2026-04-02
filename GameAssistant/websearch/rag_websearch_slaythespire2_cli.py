import argparse
import os

from openai import OpenAI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search a fixed number of Slay the Spire 2 guides."
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=8,
        help="Number of results to return (default: 8)",
    )
    return parser.parse_args()


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY environment variable.")

    args = parse_args()
    if args.count <= 0:
        raise SystemExit("--count must be a positive integer.")

    client = OpenAI(api_key=api_key)

    system_prompt = (
        "Return exactly the requested number of unique results. "
        "Output JSON only, no extra text. Each item: title, url, summary."
    )
    user_prompt = (
        f'Search for {args.count} results about "\u6740\u622e\u5c16\u58542\u653b\u7565". '
        "Prefer recent, detailed strategy guides or walkthroughs."
    )

    response = client.responses.create(
        model="gpt-5.4",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tool_choice={"type": "web_search"},
        tools=[{"type": "web_search"}],
        reasoning={"effort": "none"},
        text={"verbosity": "low"},
    )

    print(response.output_text)


if __name__ == "__main__":
    main()
