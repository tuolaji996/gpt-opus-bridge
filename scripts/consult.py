#!/usr/bin/env python3
"""Run a bounded Claude consultation through PAL's local MCP connection."""

import argparse
import asyncio
import json
import sys
from pathlib import Path


def summarize(payload, expected_model):
    """Fail closed on tool errors or absent/mismatched model metadata."""
    metadata = payload.get("metadata") or {}
    if (
        payload.get("status") == "error"
        or metadata.get("is_error")
        or metadata.get("return_code", 0) != 0
    ):
        raise ValueError("Claude did not complete successfully; no fallback was attempted.")
    reported = metadata.get("model_used")
    if reported != expected_model:
        raise ValueError("The reported model does not match the requested model; response withheld.")
    content = payload.get("content")
    if not isinstance(content, str):
        raise ValueError("PAL returned an unsupported response format.")
    return {
        "requested_model": expected_model,
        "reported_model": reported,
        "reply": content,
        "duration_seconds": metadata.get("duration_seconds"),
        "note": "Reported identity is not independent backend verification.",
    }


async def consult(args):
    # Imported here so help and offline result tests need only the standard library.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=str(args.launcher))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            arguments = {
                "cli_name": "claude",
                "role": args.role,
                "prompt": args.prompt,
            }
            if args.file:
                arguments["absolute_file_paths"] = [
                    str(Path(p).expanduser().resolve()) for p in args.file
                ]
            result = await session.call_tool("clink", arguments)
            if result.isError:
                raise ValueError("PAL returned a tool error; no fallback was attempted.")
            blocks = [c for c in result.content if c.type == "text"]
            if len(blocks) != 1:
                raise ValueError("PAL returned an unsupported response format.")
            return summarize(json.loads(blocks[0].text), args.expect_model)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument(
        "--role", choices=["codereviewer", "planner", "default", "implementer"],
        default="codereviewer",
    )
    parser.add_argument("--expect-model", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--file", action="append", default=[])
    args = parser.parse_args(argv)
    args.launcher = args.launcher.expanduser().absolute()
    if not args.launcher.is_file():
        print("Launcher does not exist.", file=sys.stderr)
        return 1
    try:
        answer = asyncio.run(asyncio.wait_for(consult(args), timeout=300))
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("Consultation interrupted.", file=sys.stderr)
        return 130
    except Exception:
        # MCP may aggregate exceptions carrying raw subprocess output or prompts.
        # Avoid printing those by default, including structured provider errors.
        print(
            "Consultation failed, timed out, or returned a different model. "
            "No fallback was attempted. Check the local PAL configuration.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(answer, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
