from __future__ import annotations

import json

import pytest
from golden import signal_desk_corpus as corpus


def _submission(index: int, family: str) -> dict:
    return {
        "id": f"sd-{index:03d}",
        "question": f"Câu hỏi số {index} về thị trường?",
        "family": family,
        "contributor": f"outside-{index % 3}",
        "expect": {"board": True, "min_kpi": 3},
    }


def _submissions(count: int = 60) -> list[dict]:
    # Enough of every family to clear its floor, then the rest spread evenly.
    out: list[dict] = []
    index = 0
    for family, floor in corpus.FAMILY_FLOORS.items():
        for _ in range(floor + 2):
            out.append(_submission(index, family))
            index += 1
    while len(out) < count:
        out.append(_submission(index, corpus.FAMILIES[index % len(corpus.FAMILIES)]))
        index += 1
    return out


def test_the_same_seed_draws_the_same_fifty_and_a_different_seed_does_not() -> None:
    submissions = _submissions()

    first = corpus.select(submissions, seed=7)
    again = corpus.select(list(reversed(submissions)), seed=7)
    other = corpus.select(submissions, seed=8)

    assert [case["id"] for case in first["cases"]] == [case["id"] for case in again["cases"]]
    assert corpus.digest(first) == corpus.digest(again)
    assert [case["id"] for case in first["cases"]] != [case["id"] for case in other["cases"]]


def test_the_draw_records_what_it_was_drawn_from() -> None:
    submissions = _submissions()

    drawn = corpus.select(submissions, seed=11)

    assert drawn["selection"]["seed"] == 11
    assert drawn["selection"]["drawn_from"] == len(submissions)
    assert drawn["selection"]["drawn"] == corpus.TARGET_CASES


def test_the_recorded_hash_ignores_file_order_and_notices_a_reworded_question() -> None:
    submissions = _submissions()
    reordered = list(reversed(submissions))
    edited = json.loads(json.dumps(submissions))
    edited[0]["question"] += " (reworded)"

    baseline = corpus.select(submissions, seed=23)["selection"]["submissions_sha256"]

    assert corpus.select(reordered, seed=23)["selection"]["submissions_sha256"] == baseline
    assert corpus.select(edited, seed=23)["selection"]["submissions_sha256"] != baseline


def test_the_draw_prefers_no_submission_for_where_it_sits_in_the_file() -> None:
    # The fixture lays families out in contiguous id blocks, so an implementation
    # that just took the first `floor` by id would satisfy every other test here.
    submissions = _submissions(80)
    first_fifty = {item["id"] for item in sorted(submissions, key=lambda i: i["id"])[:50]}

    seen: set[str] = set()
    for seed in range(40):
        seen.update(case["id"] for case in corpus.select(submissions, seed=seed)["cases"])

    assert {case["id"] for case in corpus.select(submissions, seed=0)["cases"]} != first_fifty
    assert seen == {item["id"] for item in submissions}


def test_a_pool_no_bigger_than_the_draw_refuses_rather_than_pretending_to_draw() -> None:
    submissions = _submissions(80)
    exactly_fifty = corpus.select(submissions, seed=2)["cases"]

    with pytest.raises(ValueError, match="collect more before drawing"):
        corpus.select(exactly_fifty, seed=2)


def test_every_family_floor_survives_the_draw() -> None:
    drawn = corpus.select(_submissions(), seed=3)

    counts = {family: 0 for family in corpus.FAMILIES}
    for case in drawn["cases"]:
        counts[case["family"]] += 1

    for family, floor in corpus.FAMILY_FLOORS.items():
        assert counts[family] >= floor, f"{family} fell below its floor"
    assert corpus.validate(drawn) == []


def test_every_family_short_of_its_floor_is_named_in_one_refusal() -> None:
    thin = {"off_store", "timeline"}
    submissions = [item for item in _submissions(80) if item["family"] not in thin]
    submissions += [
        _submission(900 + offset, family)
        for offset, family in enumerate(sorted(thin) * 2)
    ]

    with pytest.raises(ValueError) as error:
        corpus.select(submissions, seed=5)

    # One collection round per hidden shortfall is the cost of raising on the first.
    assert "off_store" in str(error.value)
    assert "timeline" in str(error.value)


def test_too_few_submissions_refuses() -> None:
    with pytest.raises(ValueError, match="fewer than"):
        corpus.select(_submissions()[:40], seed=5)


def test_the_drawn_corpus_does_not_share_state_with_the_submissions() -> None:
    submissions = _submissions()

    drawn = corpus.select(submissions, seed=29)
    drawn["cases"][0]["expect"]["min_kpi"] = 999

    assert all(item["expect"]["min_kpi"] == 3 for item in submissions)


def test_validate_names_every_broken_case_not_only_the_first() -> None:
    drawn = corpus.select(_submissions(), seed=13)
    drawn["cases"][0]["question"] = "  "
    drawn["cases"][1]["family"] = "vibes"
    drawn["cases"][2]["expect"] = {"board": "yes", "min_kpi": -1}
    drawn["cases"][3]["id"] = drawn["cases"][4]["id"]

    errors = corpus.validate(drawn)

    assert any("question is empty" in error for error in errors)
    assert any("'vibes'" in error for error in errors)
    assert any("expect.board" in error for error in errors)
    assert any("expect.min_kpi" in error for error in errors)
    assert any("duplicate id" in error for error in errors)


def test_the_cli_writes_a_valid_corpus_and_reports_its_digest(tmp_path, capsys) -> None:
    source = tmp_path / "submissions.json"
    source.write_text(json.dumps({"submissions": _submissions()}), encoding="utf-8")
    out = tmp_path / "signal_desk.json"

    code = corpus.main(
        ["select", "--submissions", str(source), "--seed", "17", "--out", str(out)]
    )

    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert len(written["cases"]) == corpus.TARGET_CASES
    assert corpus.digest(written) in capsys.readouterr().out
    assert corpus.main(["validate", str(out)]) == 0


def test_the_runner_stamps_the_questions_it_ran_into_the_artifact() -> None:
    from golden.run import corpus_digest

    drawn = corpus.select(_submissions(), seed=19)
    edited = json.loads(json.dumps(drawn))
    edited["cases"][0]["question"] += " (reworded between rounds)"

    assert corpus_digest(drawn) == corpus.digest(drawn)
    assert corpus_digest(edited) != corpus_digest(drawn)


def test_a_corpus_with_no_draw_behind_it_fails_the_gate() -> None:
    drawn = corpus.select(_submissions(), seed=31)
    hand_written = {key: value for key, value in drawn.items() if key != "selection"}

    assert corpus.validate(drawn) == []
    assert "selection is missing: this corpus was not drawn" in corpus.validate(hand_written)


def test_a_selection_block_that_contradicts_the_cases_fails() -> None:
    drawn = corpus.select(_submissions(), seed=37)
    drawn["selection"]["drawn_from"] = len(drawn["cases"])
    drawn["selection"]["submissions_sha256"] = ""

    errors = corpus.validate(drawn)

    assert any("drawn_from" in error for error in errors)
    assert any("submissions_sha256" in error for error in errors)


def test_a_corpus_from_another_lane_is_told_which_lane_it_is_in(capsys) -> None:
    code = corpus.main(["validate", "golden/web_first.json"])

    assert code == 1
    assert capsys.readouterr().out.strip() == (
        "not a signal_desk corpus: no case declares one of its six families"
    )


def test_the_cli_refuses_to_redraw_over_an_existing_corpus(tmp_path, capsys) -> None:
    source = tmp_path / "submissions.json"
    source.write_text(json.dumps({"submissions": _submissions()}), encoding="utf-8")
    out = tmp_path / "signal_desk.json"
    assert corpus.main(["select", "--submissions", str(source), "--seed", "41", "--out", str(out)]) == 0
    first = out.read_text(encoding="utf-8")
    capsys.readouterr()

    blocked = corpus.main(["select", "--submissions", str(source), "--seed", "42", "--out", str(out)])

    assert blocked == 1
    assert "--force" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == first
    assert corpus.main(
        ["select", "--submissions", str(source), "--seed", "42", "--out", str(out), "--force"]
    ) == 0
    assert out.read_text(encoding="utf-8") != first


def test_the_cli_names_the_operator_error_instead_of_raising(tmp_path, capsys) -> None:
    missing = tmp_path / "nope.json"
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    wrong_key = tmp_path / "wrong.json"
    wrong_key.write_text(json.dumps({"questions": _submissions()}), encoding="utf-8")

    assert corpus.main(["validate", str(missing)]) == 1
    assert corpus.main(["select", "--submissions", str(broken), "--seed", "1", "--out", str(tmp_path / "a.json")]) == 1
    assert corpus.main(["select", "--submissions", str(wrong_key), "--seed", "1", "--out", str(tmp_path / "b.json")]) == 1

    printed = capsys.readouterr().out
    assert "expected an object with a 'submissions' list" in printed
    assert "Traceback" not in printed
