"""Round-trip the three project measure files through the CQL → ELM front end."""

from __future__ import annotations

import sys
from pathlib import Path

from cql_sdk.compiler.cql_to_elm import compile_file

MEASURES = Path(
    r"c:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\cms-top"
    r"\azure-healthcare-digital-quality\orchestrator\src\measures"
)

FILES = [
    "CMS122v11_DiabetesHbA1cPoorControl.cql",
    "CMS165v9_ControllingHighBloodPressure.cql",
    "ePC02_SevereObstetricComplications.cql",
]


def main() -> int:
    failures = 0
    for filename in FILES:
        path = MEASURES / filename
        try:
            elm = compile_file(path)
            stmt_names = [s["name"] for s in elm["library"]["statements"]["def"]]
            print(f"OK  {filename}: {len(stmt_names)} statements -> {stmt_names[:3]}...")
        except Exception as exc:  # pragma: no cover - smoke util
            failures += 1
            print(f"FAIL {filename}: {type(exc).__name__}: {exc}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
