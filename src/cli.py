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
from src.types.config import Config


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _build_analyzer(config: Config) -> ImageAnalyzer:
    return ImageAnalyzer(config)


def _analyze_reference_results(
    config: Config, directory: Path, *, recursive: bool
) -> tuple[ImageAnalyzer, list[Any]]:
    analyzer = _build_analyzer(config)
    results = analyzer.analyze_directory(directory, recursive=recursive, persist=True)
    return analyzer, results


def _run_discovery(
    config: Config,
    reference_results: list[Any],
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
@click.pass_context
def analyze(ctx: click.Context, directory: Path, recursive: bool) -> None:
    analyzer, results = _analyze_reference_results(
        ctx.obj["config"], directory, recursive=recursive
    )
    summary = analyzer.summarize(results)
    JSONStore(ctx.obj["config"].output.reports_dir).export_dict(
        summary, "analysis_summary.json"
    )
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
@click.pass_context
def pipeline(
    ctx: click.Context,
    directory: Path,
    count: int,
    strategy: str,
    target_dir: Path | None,
) -> None:
    _analyzer, results = _analyze_reference_results(
        ctx.obj["config"], directory, recursive=False
    )
    benchmark = Comparator().build_profile(results).to_dict()
    manifest = _run_discovery(
        ctx.obj["config"],
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
