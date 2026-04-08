"""Unit tests for eval/results_writer.py."""

import datetime
import json
from pathlib import Path

import pytest

from eval.aggregators import ModelScore
from eval.results_writer import write_json_results, write_markdown_summary


def _make_result(model: str, scenario_id: str, c1: bool) -> dict:
    """Build a synthetic result dict for testing.

    Args:
        model: Model identifier.
        scenario_id: Scenario identifier.
        c1: Whether C1 criterion passed.

    Returns:
        A result dict matching the evaluate_scenario format.
    """
    return {
        "model": model,
        "scenario_id": scenario_id,
        "tool_calls": [],
        "agent_response": "Test response",
        "scores": {
            "criteria": {
                "C1": c1,
                "C2": True,
                "C3": True,
                "C4": True,
            },
            "details": {
                "C1": "C1 detail",
                "C2": "C2 detail",
                "C3": "C3 detail",
                "C4": "C4 detail",
            },
        },
    }


def _make_model_score(model: str, overall_pass: bool) -> ModelScore:
    """Build a synthetic ModelScore for testing.

    Args:
        model: Model identifier.
        overall_pass: Whether the model passes overall.

    Returns:
        A ModelScore object for testing.
    """
    if overall_pass:
        aggregate = 0.90
        c1_rate = 0.80
        c2_rate = 0.80
        c3_rate = 0.80
        c4_rate = 0.80
    else:
        aggregate = 0.70
        c1_rate = 0.60
        c2_rate = 0.60
        c3_rate = 0.60
        c4_rate = 0.60

    return ModelScore(
        model=model,
        aggregate_score=aggregate,
        criterion_pass_rates={
            "C1": c1_rate,
            "C2": c2_rate,
            "C3": c3_rate,
            "C4": c4_rate,
        },
        per_prompt_scores={"scenario_1": 0.75},
        passes_aggregate=overall_pass,
        passes_all_criteria=overall_pass,
        overall_pass=overall_pass,
    )


class TestWriteJsonResults:
    """Tests for write_json_results."""

    def test_write_json_results_creates_file(self, tmp_path):
        """Writing results creates a JSON file."""
        results = [
            _make_result("gpt-4.1-mini", "scenario_1", True),
            _make_result("gpt-4.1-mini", "scenario_2", False),
        ]
        output_path = write_json_results(results, str(tmp_path))
        assert Path(output_path).exists()
        assert output_path.endswith(".json")

    def test_write_json_results_correct_structure(self, tmp_path):
        """JSON output has correct structure and content."""
        results = [
            _make_result("gpt-4.1-mini", "scenario_1", True),
            _make_result("gpt-4.1-mini", "scenario_2", False),
        ]
        output_path = write_json_results(results, str(tmp_path))

        with open(output_path) as f:
            data = json.load(f)

        assert "run_date" in data
        assert "models" in data
        assert "scenarios" in data
        assert "results" in data
        assert len(data["models"]) == 1
        assert data["models"][0] == "gpt-4.1-mini"
        assert len(data["scenarios"]) == 2
        assert data["scenarios"] == ["scenario_1", "scenario_2"]
        assert len(data["results"]) == 2

    def test_write_json_results_multiple_models(self, tmp_path):
        """JSON output correctly lists all unique models."""
        results = [
            _make_result("gpt-4.1-mini", "scenario_1", True),
            _make_result("gpt-5.4-nano", "scenario_1", False),
            _make_result("gpt-4.1-mini", "scenario_2", True),
        ]
        output_path = write_json_results(results, str(tmp_path))

        with open(output_path) as f:
            data = json.load(f)

        assert len(data["models"]) == 2
        assert data["models"][0] == "gpt-4.1-mini"
        assert data["models"][1] == "gpt-5.4-nano"

    def test_write_json_results_file_path_with_trailing_slash(
        self, tmp_path
    ):
        """Directory path with trailing slash works correctly."""
        results = [_make_result("gpt-4.1-mini", "scenario_1", True)]
        path_with_slash = str(tmp_path) + "/"
        output_path = write_json_results(results, path_with_slash)
        assert Path(output_path).exists()
        assert Path(output_path).parent == tmp_path

    def test_write_json_results_explicit_models_parameter(self, tmp_path):
        """Explicit models parameter overrides extraction."""
        results = [
            _make_result("gpt-4.1-mini", "scenario_1", True),
        ]
        output_path = write_json_results(
            results,
            str(tmp_path),
            models=["gpt-4.1-mini", "gpt-5.4-nano"],
        )

        with open(output_path) as f:
            data = json.load(f)

        assert len(data["models"]) == 2
        assert data["models"] == ["gpt-4.1-mini", "gpt-5.4-nano"]


class TestWriteMarkdownSummary:
    """Tests for write_markdown_summary."""

    def test_write_markdown_summary_creates_file(self, tmp_path):
        """Writing summary creates a Markdown file."""
        scores = [_make_model_score("gpt-4.1-mini", True)]
        output_path = write_markdown_summary(scores, str(tmp_path))
        assert Path(output_path).exists()
        assert output_path.endswith(".md")

    def test_write_markdown_summary_contains_header(self, tmp_path):
        """Markdown contains date header."""
        scores = [_make_model_score("gpt-4.1-mini", True)]
        output_path = write_markdown_summary(scores, str(tmp_path))

        with open(output_path) as f:
            content = f.read()

        today = datetime.date.today().isoformat()
        assert f"# Evaluation Summary — {today}" in content

    def test_write_markdown_summary_contains_table(self, tmp_path):
        """Markdown contains decision matrix table."""
        scores = [_make_model_score("gpt-4.1-mini", True)]
        output_path = write_markdown_summary(scores, str(tmp_path))

        with open(output_path) as f:
            content = f.read()

        assert "| Model | C1% | C2% | C3% | C4% |" in content
        assert "gpt-4.1-mini" in content
        assert "mini" in content
        assert "✅ PASS" in content

    def test_write_markdown_summary_pass_fail_status(self, tmp_path):
        """Markdown shows correct pass/fail status."""
        scores = [
            _make_model_score("gpt-4.1-mini", True),
            _make_model_score("gpt-5.4-nano", False),
        ]
        output_path = write_markdown_summary(scores, str(tmp_path))

        with open(output_path) as f:
            content = f.read()

        lines = content.split("\n")
        # Find lines with model names
        mini_line = [l for l in lines if "gpt-4.1-mini" in l][0]
        nano_line = [l for l in lines if "gpt-5.4-nano" in l][0]

        assert "✅ PASS" in mini_line
        assert "❌ FAIL" in nano_line

    def test_write_markdown_summary_with_results_details(self, tmp_path):
        """Markdown includes per-model failure details when results
        provided."""
        scores = [_make_model_score("gpt-4.1-mini", False)]
        results = [
            {
                "model": "gpt-4.1-mini",
                "scenario_id": "scenario_1",
                "tool_calls": [],
                "agent_response": "test",
                "scores": {
                    "criteria": {
                        "C1": False,
                        "C2": True,
                        "C3": None,
                        "C4": True,
                    },
                    "details": {
                        "C1": "Did not call required tool",
                        "C2": "Correct",
                        "C3": "N/A",
                        "C4": "Correct",
                    },
                },
            }
        ]
        output_path = write_markdown_summary(
            scores, str(tmp_path), results=results
        )

        with open(output_path) as f:
            content = f.read()

        assert "## gpt-4.1-mini" in content
        assert "Failing scenarios:" in content
        assert "scenario_1: C1 FAIL" in content
        assert "Did not call required tool" in content

    def test_write_markdown_summary_no_failures(self, tmp_path):
        """Markdown shows 'none' for models with no failing scenarios."""
        scores = [_make_model_score("gpt-4.1-mini", True)]
        results = [
            {
                "model": "gpt-4.1-mini",
                "scenario_id": "scenario_1",
                "tool_calls": [],
                "agent_response": "test",
                "scores": {
                    "criteria": {
                        "C1": True,
                        "C2": True,
                        "C3": True,
                        "C4": True,
                    },
                    "details": {
                        "C1": "Pass",
                        "C2": "Pass",
                        "C3": "Pass",
                        "C4": "Pass",
                    },
                },
            }
        ]
        output_path = write_markdown_summary(
            scores, str(tmp_path), results=results
        )

        with open(output_path) as f:
            content = f.read()

        assert "Failing scenarios: none" in content

    def test_write_markdown_summary_recommendation_passing(
        self, tmp_path
    ):
        """Markdown recommends cheapest passing model."""
        scores = [
            _make_model_score("gpt-4.1-mini", True),
            _make_model_score("gpt-5.4-nano", True),
        ]
        output_path = write_markdown_summary(scores, str(tmp_path))

        with open(output_path) as f:
            content = f.read()

        # nano is cheaper than mini, so nano should be recommended
        assert "Cheapest passing model: **gpt-5.4-nano**" in content

    def test_write_markdown_summary_recommendation_none_passing(
        self, tmp_path
    ):
        """Markdown shows message when no models pass."""
        scores = [
            _make_model_score("gpt-4.1-mini", False),
            _make_model_score("gpt-5.4-nano", False),
        ]
        output_path = write_markdown_summary(scores, str(tmp_path))

        with open(output_path) as f:
            content = f.read()

        assert "No models passed all criteria." in content

    def test_write_markdown_summary_recommendation_alphabetical_tiebreak(
        self, tmp_path
    ):
        """Alphabetical order breaks ties within cost tier."""
        # Create two nano models, both passing
        nano1 = _make_model_score("gpt-4.1-nano", True)
        nano2 = _make_model_score("gpt-5.4-nano", True)
        scores = [nano1, nano2]
        output_path = write_markdown_summary(scores, str(tmp_path))

        with open(output_path) as f:
            content = f.read()

        # gpt-4.1-nano comes before gpt-5.4-nano alphabetically
        assert "Cheapest passing model: **gpt-4.1-nano**" in content

    def test_write_markdown_summary_file_path_with_trailing_slash(
        self, tmp_path
    ):
        """Directory path with trailing slash works correctly."""
        scores = [_make_model_score("gpt-4.1-mini", True)]
        path_with_slash = str(tmp_path) + "/"
        output_path = write_markdown_summary(scores, path_with_slash)
        assert Path(output_path).exists()
        assert Path(output_path).parent == tmp_path
