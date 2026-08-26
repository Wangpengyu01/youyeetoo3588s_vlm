#!/usr/bin/env python3
"""Parse sherpa-onnx-offline JSON output and print recognized text."""
import json
import sys


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = (obj.get("text") or "").strip()
        if text:
            print(text)
            return
    # no text found
    sys.exit(1)


if __name__ == "__main__":
    main()
