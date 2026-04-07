"""Unit tests for eval/evaluators.py — C2, C3, and C4 criteria."""

from eval.evaluators import (
    ScenarioScore,
    aggregate_model_scores,
    compute_criterion_pass_rate,
    compute_prompt_score,
    evaluate_c2_schema_valid_args,
    evaluate_c3_multi_step_sequencing,
    evaluate_c4_asks_vs_invents,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tc(tool: str, **kwargs) -> dict:
    """Build a tool-call dict in the recorder format."""
    return {"tool": tool, "arguments": kwargs}


# ---------------------------------------------------------------------------
# TEST-001: evaluate_c2_schema_valid_args
# ---------------------------------------------------------------------------


class TestC2SchemaValidArgs:
    """Tests for evaluate_c2_schema_valid_args."""

    def test_c2_all_args_present_and_matching(self):
        """All expected args are present with correct values — passes."""
        tool_calls = [
            _tc(
                "get_delegation_info",
                delegation_id="Brazil",
            )
        ]
        expected = {
            "tool_calls_ordered": [
                {
                    "name": "get_delegation_info",
                    "args_must_contain": {"delegation_id": "Brazil"},
                }
            ]
        }
        passed, detail = evaluate_c2_schema_valid_args(
            tool_calls, expected
        )
        assert passed is True
        assert isinstance(detail, str)

    def test_c2_missing_required_arg(self):
        """A required arg is absent from the actual call — fails."""
        tool_calls = [
            _tc("lookup_delegate", name="Marie Laurent")
        ]
        expected = {
            "tool_calls_ordered": [
                {
                    "name": "lookup_delegate",
                    "args_must_contain": {
                        "name": "Marie Laurent",
                        "delegation_id": "FRA",
                    },
                }
            ]
        }
        passed, detail = evaluate_c2_schema_valid_args(
            tool_calls, expected
        )
        assert passed is False
        assert "delegation_id" in detail

    def test_c2_case_insensitive_string_match(self):
        """String comparison is case-insensitive — 'marie laurent' matches
        'Marie Laurent'."""
        tool_calls = [
            _tc("lookup_delegate", name="marie laurent", delegation_id="FRA")
        ]
        expected = {
            "tool_calls_ordered": [
                {
                    "name": "lookup_delegate",
                    "args_must_contain": {
                        "name": "Marie Laurent",
                        "delegation_id": "FRA",
                    },
                }
            ]
        }
        passed, detail = evaluate_c2_schema_valid_args(
            tool_calls, expected
        )
        assert passed is True

    def test_c2_boolean_exact_match(self):
        """Boolean comparison is exact — retroactive=True expected but
        False in actual call fails."""
        tool_calls = [
            _tc(
                "create_document_access_rights",
                delegate_id="DEL-001",
                retroactive=False,
            )
        ]
        expected = {
            "tool_calls_ordered": [
                {
                    "name": "create_document_access_rights",
                    "args_must_contain": {
                        "delegate_id": "DEL-001",
                        "retroactive": True,
                    },
                }
            ]
        }
        passed, detail = evaluate_c2_schema_valid_args(
            tool_calls, expected
        )
        assert passed is False
        assert "retroactive" in detail

    def test_c2_tool_not_called(self):
        """Expected tool was never called — fails with a clear message."""
        tool_calls = [
            _tc("lookup_delegate", name="Jean Dupont")
        ]
        expected = {
            "tool_calls_ordered": [
                {
                    "name": "get_delegation_info",
                    "args_must_contain": {"delegation_id": "FRA"},
                }
            ]
        }
        passed, detail = evaluate_c2_schema_valid_args(
            tool_calls, expected
        )
        assert passed is False
        assert "get_delegation_info" in detail

    def test_c2_empty_tool_calls_ordered(self):
        """No tool calls expected — C2 not applicable, returns True."""
        passed, detail = evaluate_c2_schema_valid_args(
            [], {"tool_calls_ordered": []}
        )
        assert passed is True
        assert "not applicable" in detail.lower()

    def test_c2_empty_args_must_contain(self):
        """Tool is called but args_must_contain is empty — passes."""
        tool_calls = [_tc("get_delegation_info", delegation_id="FRA")]
        expected = {
            "tool_calls_ordered": [
                {"name": "get_delegation_info", "args_must_contain": {}}
            ]
        }
        passed, detail = evaluate_c2_schema_valid_args(
            tool_calls, expected
        )
        assert passed is True


# ---------------------------------------------------------------------------
# TEST-002: evaluate_c3_multi_step_sequencing
# ---------------------------------------------------------------------------


class TestC3MultiStepSequencing:
    """Tests for evaluate_c3_multi_step_sequencing."""

    def test_c3_correct_order(self):
        """Required tools appear in the expected relative order — passes."""
        tool_calls = [
            _tc("lookup_delegate", name="Marie Laurent"),
            _tc("get_delegation_info", delegation_id="FRA"),
            _tc("create_delegate", full_name="Marie Laurent"),
        ]
        expected = {
            "tool_calls_ordered": [
                {"name": "lookup_delegate", "args_must_contain": {}},
                {"name": "get_delegation_info", "args_must_contain": {}},
                {"name": "create_delegate", "args_must_contain": {}},
            ]
        }
        passed, detail = evaluate_c3_multi_step_sequencing(
            tool_calls, expected
        )
        assert passed is True

    def test_c3_reversed_order(self):
        """create_delegate appears before lookup_delegate — fails."""
        tool_calls = [
            _tc("create_delegate", full_name="Marie Laurent"),
            _tc("lookup_delegate", name="Marie Laurent"),
            _tc("get_delegation_info", delegation_id="FRA"),
        ]
        expected = {
            "tool_calls_ordered": [
                {"name": "lookup_delegate", "args_must_contain": {}},
                {"name": "get_delegation_info", "args_must_contain": {}},
                {"name": "create_delegate", "args_must_contain": {}},
            ]
        }
        passed, detail = evaluate_c3_multi_step_sequencing(
            tool_calls, expected
        )
        assert passed is False
        assert "create_delegate" in detail

    def test_c3_interleaved_correct_order(self):
        """Extra calls between required tools are fine — passes."""
        tool_calls = [
            _tc("lookup_delegate", name="Marie Laurent"),
            _tc("some_extra_tool"),
            _tc("get_delegation_info", delegation_id="FRA"),
            _tc("create_delegate", full_name="Marie Laurent"),
        ]
        expected = {
            "tool_calls_ordered": [
                {"name": "lookup_delegate", "args_must_contain": {}},
                {"name": "get_delegation_info", "args_must_contain": {}},
                {"name": "create_delegate", "args_must_contain": {}},
            ]
        }
        passed, detail = evaluate_c3_multi_step_sequencing(
            tool_calls, expected
        )
        assert passed is True

    def test_c3_missing_prerequisite_step(self):
        """A required tool from the sequence is never called — fails."""
        tool_calls = [
            _tc("lookup_delegate", name="Marie Laurent"),
            _tc("create_delegate", full_name="Marie Laurent"),
        ]
        expected = {
            "tool_calls_ordered": [
                {"name": "lookup_delegate", "args_must_contain": {}},
                {"name": "get_delegation_info", "args_must_contain": {}},
                {"name": "create_delegate", "args_must_contain": {}},
            ]
        }
        passed, detail = evaluate_c3_multi_step_sequencing(
            tool_calls, expected
        )
        assert passed is False
        assert "get_delegation_info" in detail

    def test_c3_single_tool_not_applicable(self):
        """Only one expected tool — sequencing not applicable, returns True."""
        tool_calls = [_tc("lookup_delegate", name="Jean Dupont")]
        expected = {
            "tool_calls_ordered": [
                {"name": "lookup_delegate", "args_must_contain": {}}
            ]
        }
        passed, detail = evaluate_c3_multi_step_sequencing(
            tool_calls, expected
        )
        assert passed is True
        assert "not applicable" in detail.lower()


# ---------------------------------------------------------------------------
# TEST-003: evaluate_c4_asks_vs_invents
# ---------------------------------------------------------------------------


class TestC4AsksVsInvents:
    """Tests for evaluate_c4_asks_vs_invents."""

    def test_c4_should_ask_and_does_ask(self):
        """should_ask=True, no write tools called, response ends with '?'
        — passes."""
        tool_calls = [_tc("lookup_delegate", name="Jean Dupont")]
        agent_response = "Could you please provide Jean Dupont's email?"
        expected = {
            "should_ask_user": True,
            "must_not_hallucinate": ["email"],
        }
        passed, detail = evaluate_c4_asks_vs_invents(
            tool_calls, agent_response, expected
        )
        assert passed is True

    def test_c4_should_ask_but_calls_create(self):
        """should_ask=True but create_delegate was called — fails."""
        tool_calls = [
            _tc("create_delegate", full_name="Jean Dupont", email="x@x.com")
        ]
        agent_response = "I have created the delegate for you."
        expected = {
            "should_ask_user": True,
            "must_not_hallucinate": ["email"],
        }
        passed, detail = evaluate_c4_asks_vs_invents(
            tool_calls, agent_response, expected
        )
        assert passed is False
        assert "create_delegate" in detail

    def test_c4_should_ask_but_no_question(self):
        """should_ask=True, no write tool, but no question in response
        — fails."""
        tool_calls = []
        agent_response = "I cannot complete this task without more details."
        expected = {
            "should_ask_user": True,
            "must_not_hallucinate": ["email"],
        }
        passed, detail = evaluate_c4_asks_vs_invents(
            tool_calls, agent_response, expected
        )
        assert passed is False
        assert "question" in detail.lower()

    def test_c4_should_not_ask_empty_must_not_hallucinate(self):
        """should_ask=False, must_not_hallucinate is empty — passes."""
        tool_calls = [_tc("lookup_delegate", name="Marie Laurent")]
        agent_response = "Marie Laurent is in the FRA delegation."
        expected = {
            "should_ask_user": False,
            "must_not_hallucinate": [],
        }
        passed, detail = evaluate_c4_asks_vs_invents(
            tool_calls, agent_response, expected
        )
        assert passed is True
        assert "no hallucination fields" in detail.lower()

    def test_c4_should_not_ask_no_write_tools(self):
        """should_ask=False, only read tools called — deferred check,
        passes."""
        tool_calls = [
            _tc("get_delegation_info", delegation_id="FRA"),
            _tc("lookup_delegate", name="Marie Laurent"),
        ]
        agent_response = "Here is the delegation info."
        expected = {
            "should_ask_user": False,
            "must_not_hallucinate": ["email", "committee_ids"],
        }
        passed, detail = evaluate_c4_asks_vs_invents(
            tool_calls, agent_response, expected
        )
        assert passed is True
        assert "deferred" in detail.lower()


# ---------------------------------------------------------------------------
# TEST-004: compute_prompt_score, compute_criterion_pass_rate,
#           aggregate_model_scores
# ---------------------------------------------------------------------------


class TestAggregateModelScores:
    """Tests for compute_prompt_score, compute_criterion_pass_rate,
    and aggregate_model_scores."""

    def _all_pass_score(self, scenario_id: str) -> ScenarioScore:
        """Build a ScenarioScore with all four criteria passing."""
        return ScenarioScore(
            scenario_id=scenario_id,
            criteria={"C1": True, "C2": True, "C3": True, "C4": True},
            details={},
        )

    # --- compute_prompt_score ---

    def test_prompt_score_two_of_three_applicable(self):
        """2 passing / 3 applicable criteria → score ≈ 0.667."""
        score = ScenarioScore(
            scenario_id="s1",
            criteria={
                "C1": True,
                "C2": False,
                "C3": True,
                "C4": None,
            },
            details={},
        )
        result = compute_prompt_score(score)
        assert abs(result - 2 / 3) < 1e-9

    def test_prompt_score_no_applicable_criteria(self):
        """0 applicable criteria → score is 0.0."""
        score = ScenarioScore(
            scenario_id="s2",
            criteria={"C1": None, "C2": None, "C3": None, "C4": None},
            details={},
        )
        result = compute_prompt_score(score)
        assert result == 0.0

    # --- compute_criterion_pass_rate ---

    def test_criterion_pass_rate_all_passing(self):
        """All scenarios pass C1 → rate is 1.0."""
        scores = [self._all_pass_score(f"s{i}") for i in range(5)]
        rate = compute_criterion_pass_rate(scores, "C1")
        assert rate == 1.0

    def test_criterion_pass_rate_none_applicable(self):
        """No scenario has C1 applicable → vacuously 1.0."""
        scores = [
            ScenarioScore(
                scenario_id=f"s{i}",
                criteria={"C1": None, "C2": True},
                details={},
            )
            for i in range(3)
        ]
        rate = compute_criterion_pass_rate(scores, "C1")
        assert rate == 1.0

    def test_criterion_pass_rate_partial(self):
        """3 of 4 applicable scenarios pass C2 → rate is 0.75."""
        criteria_values = [True, True, True, False]
        scores = [
            ScenarioScore(
                scenario_id=f"s{i}",
                criteria={"C2": val},
                details={},
            )
            for i, val in enumerate(criteria_values)
        ]
        rate = compute_criterion_pass_rate(scores, "C2")
        assert rate == 0.75

    # --- aggregate_model_scores ---

    def test_aggregate_all_pass(self):
        """15 scenarios all passing → aggregate_score 1.0, overall_pass."""
        scores = [self._all_pass_score(f"s{i}") for i in range(15)]
        result = aggregate_model_scores("gpt-4o", scores)

        assert result.model == "gpt-4o"
        assert result.aggregate_score == 1.0
        assert result.passes_aggregate is True
        assert result.passes_all_criteria is True
        assert result.overall_pass is True
        assert len(result.per_prompt_scores) == 15

    def test_aggregate_below_threshold(self):
        """Low-scoring scenarios → passes_aggregate=False, overall_pass=F."""
        # 4 criteria, 1 passing → prompt score 0.25 each
        scores = [
            ScenarioScore(
                scenario_id=f"s{i}",
                criteria={
                    "C1": True,
                    "C2": False,
                    "C3": False,
                    "C4": False,
                },
                details={},
            )
            for i in range(10)
        ]
        result = aggregate_model_scores("gpt-4o-mini", scores)

        assert result.aggregate_score == 0.25
        assert result.passes_aggregate is False
        assert result.overall_pass is False

    def test_aggregate_criterion_below_threshold(self):
        """One criterion passes < 75% → passes_all_criteria=False."""
        # C2 fails on 3 of 4 scenarios (25% pass rate)
        scores = [
            ScenarioScore(
                scenario_id=f"s{i}",
                criteria={
                    "C1": True,
                    "C2": True if i == 0 else False,
                    "C3": True,
                    "C4": True,
                },
                details={},
            )
            for i in range(4)
        ]
        result = aggregate_model_scores("some-model", scores)

        assert result.criterion_pass_rates["C2"] == 0.25
        assert result.passes_all_criteria is False
        assert result.overall_pass is False
