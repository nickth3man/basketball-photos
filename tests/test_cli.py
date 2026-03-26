from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from src.cli import cli


class TestCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_analyze_command_outputs_summary_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = {"total_photos": 1, "average_score": 7.2}

            with (
                patch("src.cli.ImageAnalyzer") as analyzer_class,
                patch("src.cli.JSONStore") as json_store_class,
            ):
                analyzer = analyzer_class.return_value
                analyzer.analyze_directory.return_value = [MagicMock()]
                analyzer.summarize.return_value = summary

                result = self.runner.invoke(cli, ["analyze", "--directory", tmpdir])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(json.loads(result.output), summary)
            analyzer.analyze_directory.assert_called_once_with(
                Path(tmpdir), recursive=False, persist=True
            )
            json_store_class.return_value.export_dict.assert_called_once()

    def test_discover_command_outputs_acceptance_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "downloads"

            with (
                patch("src.cli.ImageAnalyzer") as analyzer_class,
                patch("src.cli.PhotoDiscovery") as discovery_class,
            ):
                analyzer_class.return_value.analyze_directory.return_value = [
                    "reference"
                ]
                discovery_class.return_value.discover.return_value = {
                    "accepted": [{"file_path": "one.jpg"}],
                    "threshold": 7.0,
                }

                result = self.runner.invoke(
                    cli,
                    [
                        "discover",
                        "--directory",
                        tmpdir,
                        "--count",
                        "2",
                        "--strategy",
                        "median",
                        "--target-dir",
                        str(target_dir),
                    ],
                )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                json.loads(result.output), {"accepted": 1, "threshold": 7.0}
            )
            discovery_class.return_value.discover.assert_called_once_with(
                ["reference"],
                count=2,
                strategy="median",
                output_dir=target_dir,
            )

    def test_pipeline_command_outputs_benchmark_and_acceptance_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.cli.ImageAnalyzer") as analyzer_class,
                patch("src.cli.PhotoDiscovery") as discovery_class,
                patch("src.cli.Comparator") as comparator_class,
            ):
                analyzer_class.return_value.analyze_directory.return_value = [
                    "reference"
                ]
                comparator_class.return_value.build_profile.return_value.to_dict.return_value = {
                    "average_overall": 6.5,
                    "max_overall": 8.0,
                }
                discovery_class.return_value.discover.return_value = {
                    "accepted": [{"file_path": "one.jpg"}, {"file_path": "two.jpg"}]
                }

                result = self.runner.invoke(
                    cli,
                    ["pipeline", "--directory", tmpdir, "--count", "2"],
                )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                json.loads(result.output),
                {"analysis_average": 6.5, "analysis_max": 8.0, "accepted": 2},
            )


if __name__ == "__main__":
    unittest.main()
