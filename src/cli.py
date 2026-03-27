from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

import click

from src import __version__
from src.analyzer.image_analyzer import ImageAnalyzer
from src.config import load_config
from src.grader.comparator import Comparator
from src.scraper.photo_discovery import PhotoDiscovery
from src.storage.json_store import JSONStore
from src.types.analysis import AnalysisResult
from src.types.config import Config


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _build_analyzer(config: Config) -> ImageAnalyzer:
    return ImageAnalyzer(config)


def _analyze_reference_results(
    config: Config,
    directory: Path,
    *,
    recursive: bool,
    team_hint: str | None = None,
) -> tuple[ImageAnalyzer, list[AnalysisResult]]:
    analyzer = _build_analyzer(config)
    results = analyzer.analyze_directory(
        directory,
        recursive=recursive,
        persist=True,
        team_hint=team_hint,
    )
    return analyzer, results


def _run_discovery(
    config: Config,
    reference_results: list[AnalysisResult],
    *,
    count: int,
    strategy: str,
    target_dir: Path | None,
) -> dict[str, object]:
    return PhotoDiscovery(config).discover(
        reference_results,
        count=count,
        strategy=strategy,
        output_dir=target_dir,
    )


@click.group()
@click.option("--config-path", type=click.Path(path_type=Path), default=None)
@click.option("--verbose", is_flag=True, default=False)
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None, verbose: bool) -> None:
    configure_logging(verbose)
    ctx.obj = {"config": load_config(config_path)}


@cli.command()
@click.option(
    "--directory", type=click.Path(path_type=Path, exists=True), required=True
)
@click.option("--recursive/--no-recursive", default=False)
@click.option(
    "--identify-players/--no-identify-players",
    default=None,
    help="Enable/disable player identification (overrides config)",
)
@click.option(
    "--team",
    default=None,
    help="Team abbreviation for roster matching (e.g., LAL, BOS)",
)
@click.option(
    "--export-review-queue",
    type=click.Path(path_type=Path),
    default=None,
    help="Export review queue to directory",
)
@click.pass_context
def analyze(
    ctx: click.Context,
    directory: Path,
    recursive: bool,
    identify_players: bool | None,
    team: str | None,
    export_review_queue: Path | None,
) -> None:
    config = ctx.obj["config"]

    if identify_players is not None:
        config.player_identification.enabled = identify_players

    analyzer, results = _analyze_reference_results(
        config, directory, recursive=recursive, team_hint=team
    )

    if export_review_queue and config.player_identification.enabled:
        from src.storage.review_queue import ReviewQueueExporter, create_review_queue

        review_items = create_review_queue(results)
        if review_items:
            exporter = ReviewQueueExporter(export_review_queue)
            exporter.export_to_json(review_items)
            exporter.export_to_csv(review_items)
            click.echo(f"Exported {len(review_items)} items for review")

    summary = analyzer.summarize(results)
    JSONStore(config.output.reports_dir).export_dict(summary, "analysis_summary.json")
    click.echo(json.dumps(summary, indent=2))


@cli.command()
@click.option(
    "--directory", type=click.Path(path_type=Path, exists=True), required=True
)
@click.option("--count", type=int, default=3, show_default=True)
@click.option(
    "--strategy",
    type=click.Choice(["all", "average", "median", "blend"]),
    default="all",
    show_default=True,
)
@click.option("--target-dir", type=click.Path(path_type=Path), default=None)
@click.pass_context
def discover(
    ctx: click.Context,
    directory: Path,
    count: int,
    strategy: str,
    target_dir: Path | None,
) -> None:
    _analyzer, reference_results = _analyze_reference_results(
        ctx.obj["config"], directory, recursive=False
    )
    manifest = _run_discovery(
        ctx.obj["config"],
        reference_results,
        count=count,
        strategy=strategy,
        target_dir=target_dir,
    )
    accepted = cast(list[dict[str, Any]], manifest.get("accepted", []))
    click.echo(
        json.dumps(
            {"accepted": len(accepted), "threshold": manifest.get("threshold")},
            indent=2,
        )
    )


@cli.command()
@click.option(
    "--directory", type=click.Path(path_type=Path, exists=True), required=True
)
@click.option("--count", type=int, default=3, show_default=True)
@click.option(
    "--strategy",
    type=click.Choice(["all", "average", "median", "blend"]),
    default="all",
    show_default=True,
)
@click.option("--target-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--identify-players/--no-identify-players",
    default=None,
    help="Enable/disable player identification (overrides config)",
)
@click.option(
    "--team",
    default=None,
    help="Team abbreviation for roster matching (e.g., LAL, BOS)",
)
@click.pass_context
def pipeline(
    ctx: click.Context,
    directory: Path,
    count: int,
    strategy: str,
    target_dir: Path | None,
    identify_players: bool | None,
    team: str | None,
) -> None:
    config = ctx.obj["config"]

    if identify_players is not None:
        config.player_identification.enabled = identify_players

    _analyzer, results = _analyze_reference_results(
        config, directory, recursive=False, team_hint=team
    )
    benchmark = Comparator().build_profile(results).to_dict()
    manifest = _run_discovery(
        config,
        results,
        count=count,
        strategy=strategy,
        target_dir=target_dir,
    )
    accepted = cast(list[dict[str, Any]], manifest.get("accepted", []))
    click.echo(
        json.dumps(
            {
                "analysis_average": benchmark["average_overall"],
                "analysis_max": benchmark["max_overall"],
                "accepted": len(accepted),
            },
            indent=2,
        )
    )
