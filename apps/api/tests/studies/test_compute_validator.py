"""What the calculation validator refuses, and the invariant each refusal holds.

The whole reason a model may write code here is that the code cannot smuggle a
market number in. So these are not style rules with tests attached: each one is
the enforcement of a promise made somewhere a reader can see it — that every
figure on a Signal Desk came from data, that a calculation reaches no file and
no socket, and that a rejected calculation says why in a way the next round can
act on.
"""

from __future__ import annotations

import pytest

from src.studies.compute import validator


def codes(code: str) -> set[str]:
    return {violation.code for violation in validator.validate(code)}


# -- the numbers ---------------------------------------------------------------


def test_a_figure_typed_into_the_code_is_refused_by_name():
    """The invariant the whole tool exists under, at its narrowest.

    ``0.045`` is a plausible cost of equity and there is no way to tell it from
    a measured one once it is inside an expression. So it never gets inside one.
    """
    assert validator.LITERAL_NUMBER in codes("result = f0['roe'] - 0.045")


def test_a_structural_number_is_not_a_figure():
    """A percentage's hundred and a year's sessions describe shape, not a market."""
    assert codes("result = f0['ratio'] * 100 / 252") == set()


def test_the_small_counts_are_structural_and_the_ones_past_twelve_are_not():
    assert codes("result = f0.shift(12)") == set()
    assert validator.LITERAL_NUMBER in codes("result = f0.shift(13)")


def test_a_rolling_window_of_twenty_sessions_has_to_be_declared():
    """The case the constants door exists for, and the one most likely to annoy.

    Twenty sessions is a judgement about how long a trend takes to show, which is
    exactly the kind of assumption a reader should see stated rather than find
    inside an expression.
    """
    assert validator.LITERAL_NUMBER in codes("result = f0.rolling(20).mean()")
    assert codes("result = f0.rolling(window).mean()") == set()


def test_an_index_is_a_position_rather_than_a_claim():
    assert codes("result = f0.iloc[:, 37]") == set()
    assert codes("result = f0[f0.columns[17]].to_frame()") == set()


def test_a_row_count_and_a_rounding_are_positions_too():
    assert codes("result = f0.head(50)") == set()
    assert codes("result = f0.tail(200).round(3)") == set()
    assert codes("result = f0.nlargest(25, 'adtv')") == set()


def test_a_boolean_is_not_a_number():
    assert codes("result = f0[f0['ok'] == True]") == set()


def test_a_negative_figure_is_caught_through_its_sign():
    assert validator.LITERAL_NUMBER in codes("result = f0['x'] + -0.5")


def test_a_scale_written_in_exponent_form_is_still_the_same_scale():
    """``1e9`` and ``1_000_000_000`` are one number written two ways."""
    assert codes("result = f0['value'] / 1e9") == set()


# -- the sandbox ---------------------------------------------------------------


def test_an_import_outside_the_five_is_refused():
    assert validator.FORBIDDEN_IMPORT in codes("import socket\nresult = f0")
    assert validator.FORBIDDEN_IMPORT in codes("from os import path\nresult = f0")


def test_the_five_are_allowed():
    assert codes("import math\nimport numpy as np\nresult = f0 * np.nan") == set()


def test_a_name_that_reaches_outside_is_refused():
    for name in ("open", "eval", "exec", "__import__", "getattr", "globals"):
        assert validator.FORBIDDEN_NAME in codes(f"result = {name}('x')"), name


def test_a_dunder_is_refused_as_a_family_rather_than_one_at_a_time():
    """Every published escape from a restricted namespace walks one of these.

    A list of the ones known today is a list that goes stale the next time
    somebody finds a fourth, so the shape is refused instead of the members.
    """
    assert validator.FORBIDDEN_NAME in codes("result = ().__class__")
    assert validator.FORBIDDEN_NAME in codes("result = __builtins__")
    assert validator.FORBIDDEN_NAME in codes("result = f0.__class__.__bases__")


def test_reading_or_writing_the_world_through_pandas_is_refused():
    """The hole the name list alone leaves open: ``pd`` is in the namespace."""
    assert validator.FORBIDDEN_NAME in codes("result = pd.read_csv('/etc/passwd')")
    assert validator.FORBIDDEN_NAME in codes("result = f0.to_parquet('x')")


def test_the_pure_conversions_that_share_the_prefix_are_still_allowed():
    assert codes("result = f0['x'].to_frame()") == set()
    assert codes("result = pd.to_datetime(f0['session']).to_frame()") == set()
    assert codes("result = f0['x'].to_numpy().sum().to_frame()") == set()


# -- the shape of the answer ---------------------------------------------------


def test_code_that_never_names_result_is_refused_before_a_process_is_spawned():
    assert validator.NO_RESULT in codes("f0.mean()")


def test_an_augmented_or_annotated_assignment_still_counts_as_naming_it():
    assert validator.NO_RESULT not in codes("result = f0\nresult += f0")


def test_code_python_cannot_read_is_one_violation_and_not_a_crash():
    found = validator.validate("result = f0[")

    assert [violation.code for violation in found] == [validator.SYNTAX_ERROR]


# -- what a refusal is for -----------------------------------------------------


def test_every_reason_comes_back_at_once():
    """A model handed one mistake per round would spend the Turn on spelling.

    Four rounds is the whole budget, so a validator that reported the first
    violation would make a calculation with three mistakes unfixable.
    """
    found = validator.validate("import socket\nresult = f0 * 0.07 + open('x')")

    assert {violation.code for violation in found} == {
        validator.FORBIDDEN_IMPORT,
        validator.LITERAL_NUMBER,
        validator.FORBIDDEN_NAME,
    }


def test_a_violation_says_where_to_look():
    found = validator.validate("result = f0\nresult = result * 0.07")

    assert found[0].line == 2
    assert "0.07" in found[0].snippet
    assert "constants" in found[0].detail


def test_the_first_code_is_the_one_the_tool_answers_with():
    found = validator.validate("result = f0 * 0.07")

    assert validator.first_code(found) == validator.LITERAL_NUMBER
    assert validator.first_code(()) == ""


# -- the two routes the first version left open --------------------------------


def test_a_threshold_inside_brackets_is_not_a_position():
    """The hole the first version had, and the most natural way to have it.

    Everything under a subscript was exempt, on the reasoning that a subscript
    holds an index. ``f0[f0['roe'] > 0.05]`` is a subscript holding a *filter*,
    and 0.05 in it is a claim about what a good return on equity is.
    """
    assert validator.LITERAL_NUMBER in codes("result = f0[f0['roe'] > 0.05]")
    assert validator.LITERAL_NUMBER in codes("result = f0[f0['x'].abs() < 0.5]")


def test_an_index_and_a_slice_bound_are_still_positions():
    """And the fix does not close the thing the exemption was for."""
    assert codes("result = f0.iloc[0:37]") == set()
    assert codes("result = f0.iloc[37]") == set()
    assert codes("result = f0.iloc[::37]") == set()
    assert codes("result = f0.iloc[37, 15]") == set()


def test_a_figure_with_quotes_around_it_is_still_a_figure():
    """``float("0.07")`` reads exactly like typing ``0.07``."""
    assert validator.LITERAL_NUMBER in codes("result = f0 * float('0.07')")
    assert validator.LITERAL_NUMBER in codes("result = f0['x'].astype('0.07')")


def test_a_numeric_looking_label_that_is_not_being_coerced_is_a_label():
    """A pivoted table has a column called ``2025``, and it is not a claim."""
    assert codes("result = f0[['2025', '2026']]") == set()
    assert codes("result = f0.rename(columns={'a': '2025'})") == set()


def test_structural_arithmetic_reaches_any_number_and_that_is_written_down():
    """The honest limit, asserted so nobody discovers it as a surprise.

    ``7 / 100`` is 0.07 and every part of it is structural. No reading of the
    code separates that from a percentage the question actually called for. What
    the validator closes is every obvious route, each by name; what makes a
    number real is that it came out of a frame, one layer up.
    """
    assert codes("result = f0 * 7 / 100") == set()
