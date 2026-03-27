from __future__ import annotations

import json
from typing import Any


def format_analysis_summary(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2)


def format_discovery_summary(manifest: dict[str, object]) -> str:
    accepted = manifest.get("accepted", [])
    return json.dumps(
        {
            "accepted": len(accepted) if isinstance(accepted, list) else accepted,
            "threshold": manifest.get("threshold"),
        },
        indent=2,
    )


def format_pipeline_summary(
    benchmark: dict[str, Any], manifest: dict[str, object]
) -> str:
    accepted = manifest.get("accepted", [])
    return json.dumps(
        {
            "analysis_average": benchmark["average_overall"],
            "analysis_max": benchmark["max_overall"],
            "accepted": len(accepted) if isinstance(accepted, list) else accepted,
        },
        indent=2,
    )
