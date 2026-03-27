from __future__ import annotations

from pathlib import Path

import click


directory_option = click.option(
    "--directory",
    type=click.Path(path_type=Path, exists=True),
    required=True,
)

recursive_option = click.option(
    "--recursive/--no-recursive",
    default=False,
)

count_option = click.option(
    "--count",
    type=int,
    default=3,
    show_default=True,
)

strategy_option = click.option(
    "--strategy",
    type=click.Choice(["all", "average", "median", "blend"]),
    default="all",
    show_default=True,
)

target_dir_option = click.option(
    "--target-dir",
    type=click.Path(path_type=Path),
    default=None,
)
