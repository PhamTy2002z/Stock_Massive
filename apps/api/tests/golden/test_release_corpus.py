"""The release corpus is data the graders trust, so the data is checked too.

Every rule here is one the graders assume without asserting: that a declaration
they read exists, that a marker they match on is used by somebody, that a
dimension they emit is one the corpus classifies. A corpus that drifts from
those assumptions does not crash — it quietly stops deciding, which is the
failure mode both previous eval batteries died of.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
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


def test_every_frozen_figure_names_the_page_it_came_off(corpus):
    """A ground-truth number with no source is a fabricated one.

    The protection has not moved since the corpus was empty; only its shape
    has. Then, the way to avoid inventing truth was to declare every case
    pending. Now that curation has happened, the way is to demand of each value
    what curation was supposed to produce: a number a grader can parse, the unit
    it is in, and the URL and publication date of the page it was read off.

    A case may still carry no values, and that is not a lesser state — it scores
    ``None`` rather than a pass. What it may not do is stay silent about why:
    the status has to say what happened, so a reader can tell work-not-done from
    a figure no source states.
    """
    material = [c for c in corpus["cases"] if c["family"] == "material_claim_accuracy"]
    assert material
    for case in material:
        truth = case["ground_truth"]
        status = truth.get("status") or ""
        assert status, f"{case['id']} declares no ground-truth status"
        if not truth["values"]:
            # Long enough to be an explanation rather than a label.
            assert len(truth.get("note") or "") > 40, (
                f"{case['id']} froze nothing and does not say why"
            )
            continue
        for value in truth["values"]:
            assert Decimal(str(value["value"]))
            assert value["unit"]
            assert str(value["source"]).startswith("https://")
            assert value["published_at"]
            assert Decimal(str(value["tolerance"])) >= 0


def test_every_curated_date_is_a_date_and_says_how_it_was_read(corpus):
    """A date here is read off the page, and the map records how.

    Filling this map by guessing would fabricate the very ground truth
    ``temporal_validity`` exists to check, so the rule is not that the map be
    full — it is that every entry in it be a parseable date with a recorded
    extraction method and confidence, and that the note carry the coverage
    measurement rather than a promise.

    ``evidence_dates`` stays flat because the grader reads it with ``as_date``;
    the provenance lives in its own map so that a nested object can never turn
    a date into something ``as_date`` refuses.
    """
    dates = corpus["evidence_dates"]
    provenance = corpus["evidence_date_provenance"]
    assert "publication time" in dates["note"]
    curated = {url: value for url, value in dates.items() if url != "note"}
    assert curated, "no source is dated, so temporal_validity can only report BLIND"
    for url, value in curated.items():
        assert url.startswith("https://")
        assert date.fromisoformat(str(value)[:10])
        assert provenance[url]["method"] in {
            "provider", "html_meta", "json_ld", "visible_text", "url_pattern"
        }
        assert provenance[url]["confidence"] in {"high", "medium", "low"}
    assert set(provenance) == set(curated)
