from __future__ import annotations

import json

from observability.metrics import (
    build_observability_report,
)


def main() -> None:
    report = (
        build_observability_report()
    )

    print(
        json.dumps(
            report,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
