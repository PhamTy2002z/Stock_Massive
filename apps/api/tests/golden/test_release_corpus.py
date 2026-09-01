"""The release corpus is data the graders trust, so the data is checked too.

Every rule here is one the graders assume without asserting: that a declaration
they read exists, that a marker they match on is used by somebody, that a
dimension they emit is one the corpus classifies. A corpus that drifts from
those assumptions does not crash — it quietly stops deciding, which is the
failure mode both previous eval batteries died of.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from golden.grade import GRADERS
from golden.graders import DIMENSIONS

CORPUS_PATH = Path(__file__).resolve().parents[2] / "golden" / "release.json"

#: Every key a case may declare under ``expect``. A key outside this set is a
#: declaration no grader reads, which reads as a requirement and enforces
#: nothing.
KNOWN_EXPECT_KEYS = {
    "min_distinct_domains",
    "min_pages_read",
    "must_cite_external_numbers",
    "must_refuse",
    "must_disclose_conflict",
    "must_disclose_gap",
    "must_label_assumption",
    "must_ask",
    "must_not_ask",
    "ask_budget",
}

#: The four jobs of roadmap §1 plus the five answer shapes §10 Phase 1 adds.
REQUIRED_FAMILIES = {
    "thesis_check",
    "event_memo",
    "fact_verification",
    "source_conflict",
    "fact_lookup",
    "weekly_movement",
    "outlook",
    "missing_data",
    "recommendation",
    "elicitation_quality",
    "material_claim_accuracy",
}


@pytest.fixture(scope="module")
def corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def test_the_corpus_declares_its_schema(corpus):
    assert corpus["schema"] == "golden.corpus@1"
    assert corpus["corpus_id"] == "release-v1"


def test_every_family_roadmap_names_has_cases(corpus):
    families = {case["family"] for case in corpus["cases"]}
    assert REQUIRED_FAMILIES <= families
    # And nothing is declared that no case uses: a family description nobody
    # instantiates is a family the judge would be shown for a case that does
    # not exist.
    assert set(corpus["families"]) == families


def test_case_ids_are_unique(corpus):
    ids = [case["id"] for case in corpus["cases"]]
    assert len(set(ids)) == len(ids)


def test_every_expect_key_is_one_a_grader_reads(corpus):
    used = {key for case in corpus["cases"] for key in case.get("expect", {})}
    assert used <= KNOWN_EXPECT_KEYS, used - KNOWN_EXPECT_KEYS


def test_every_case_says_why_a_fluent_answer_fails(corpus):
    for case in corpus["cases"]:
        assert case["question"].strip()
        assert case["why_a_fluent_answer_fails"].strip()
        assert case["traps"], f"{case['id']} declares no trap"


def test_the_dimension_table_covers_every_grader(corpus):
    declared = set(corpus["dimensions"])
    assert declared == set(GRADERS)
    for name in DIMENSIONS:
        assert corpus["dimensions"][name]["class"] in {"hard", "reported"}


def test_the_hard_dimensions_are_the_ones_the_roadmap_names(corpus):
    hard = {name for name, body in corpus["dimensions"].items() if body["class"] == "hard"}
    assert hard == {
        "settlement",
        "citation_url",
        "evidence_identity",
        "material_claim",
        "temporal_validity",
        "refusal_policy",
        "budget",
    }


def test_temporal_cases_pin_an_as_of_in_the_past(corpus):
    pinned = [case for case in corpus["cases"] if case.get("as_of")]
    assert pinned, "no case pins an as_of, so temporal_validity can never fail"
    for case in pinned:
        assert case["as_of"] < corpus["created"]


def test_refusal_cases_exist_and_the_vocabulary_is_used(corpus):
    refusing = [c for c in corpus["cases"] if c.get("expect", {}).get("must_refuse")]
    assert len(refusing) >= 3
    assert corpus["markers"]["refusal"] and corpus["markers"]["advice"]


def test_ground_truth_is_declared_pending_rather_than_invented(corpus):
    frozen = [c for c in corpus["cases"] if c["family"] == "material_claim_accuracy"]
    assert frozen
    for case in frozen:
        truth = case["ground_truth"]
        # Empty on purpose until a record run exists. A value written here
        # before anybody read a page would be a fabricated ground truth, which
        # is worse than no ground truth at all.
        assert truth["values"] == []
        assert truth["status"] == "pending_record_run"


def test_evidence_dates_are_empty_and_say_what_blocks_them(corpus):
    """Empty is the honest state, and the note has to name the blocker.

    Filling this map by guessing dates would fabricate the very ground truth
    ``temporal_validity`` exists to check, so the corpus carries the measurement
    that explains the gap instead of a plausible-looking date.
    """
    dates = corpus["evidence_dates"]
    assert set(dates) == {"note"}
    assert "publication time" in dates["note"]
