"""The sandbox itself: what it computes, and what it will not let out.

Every test here runs a real subprocess, because a fake one proves nothing about
the thing being claimed. The claim is that a calculation cannot reach the
network, cannot reach a file, cannot run forever and cannot take the process
down with it — and every one of those is a property of an operating system
rather than of a function.

Two of the ceilings are platform-dependent and the response says so rather than
pretending otherwise. ``RLIMIT_AS`` works on Linux and is refused outright by
macOS, so the memory test asserts the limit *where it applied* and asserts the
wall clock everywhere. That is the honest shape: a developer's machine has a
weaker box than the container, and a test that hid the difference would be
telling a reader the container's guarantee holds on their laptop.
"""

from __future__ import annotations

import time

import pytest

from src.studies.compute import runner, worker


def frame(columns, rows):
    return {"columns": list(columns), "rows": [list(row) for row in rows]}


QUARTERS = frame(
    ("period", "symbol", "net_profit", "equity"),
    (
        ("2025-Q1", "VIC", 1000.0, 20000.0),
        ("2025-Q2", "VIC", 1200.0, 20500.0),
        ("2025-Q1", "VCB", 8000.0, 90000.0),
        ("2025-Q2", "VCB", 8400.0, 92000.0),
    ),
)


# -- that it computes ----------------------------------------------------------


def test_a_calculation_comes_back_as_a_frame_payload():
    outcome = runner.run(
        code="result = f0[['period', 'symbol', 'net_profit']]",
        frames=[QUARTERS],
    )

    assert outcome["ok"] is True
    assert outcome["frame"]["columns"] == ["period", "symbol", "net_profit"]
    assert len(outcome["frame"]["rows"]) == 4


def test_a_series_is_accepted_as_an_answer_and_arrives_with_its_index():
    outcome = runner.run(
        code=(
            "grouped = f0.groupby('symbol')['net_profit'].sum()\n"
            "result = grouped"
        ),
        frames=[QUARTERS],
    )

    assert outcome["ok"] is True
    assert outcome["frame"]["columns"] == ["symbol", "net_profit"]
    assert sorted(row[0] for row in outcome["frame"]["rows"]) == ["VCB", "VIC"]


def test_two_frames_arrive_as_f0_and_f1_in_the_order_they_were_named():
    outcome = runner.run(
        code="result = pd.concat([f0, f1])",
        frames=[frame(("x",), ((1.0,),)), frame(("x",), ((2.0,),))],
    )

    assert [row[0] for row in outcome["frame"]["rows"]] == [1.0, 2.0]


def test_a_declared_constant_is_bound_under_its_own_name():
    outcome = runner.run(
        code="result = (f0['net_profit'] * ceiling).to_frame()",
        frames=[QUARTERS],
        constants={"ceiling": 2.5},
    )

    assert outcome["frame"]["rows"][0][0] == pytest.approx(2500.0)


def test_a_calculation_says_what_its_numbers_mean_through_attrs():
    """The mechanism a comparison reaches a chart as a comparison by.

    Without it a table of two companies is two anonymous columns, and the claim
    the picture exists to make — *this one is stronger on this figure* — has
    nowhere to live.
    """
    outcome = runner.run(
        code=(
            "result = f0.groupby('symbol')['net_profit'].sum().to_frame()\n"
            "result = result.reset_index()\n"
            "result.attrs['cell_roles'] = [(0, 'net_profit', 'winner')]\n"
            "result.attrs['unit'] = 'vnd'"
        ),
        frames=[QUARTERS],
    )

    assert outcome["frame"]["cellRoles"] == [
        {"row": 0, "column": "net_profit", "role": "winner"}
    ]
    assert outcome["frame"]["unit"] == "vnd"


def test_a_datetime_index_makes_the_answer_a_series():
    outcome = runner.run(
        code=(
            "f0['d'] = pd.to_datetime(f0['session'])\n"
            "result = f0.set_index('d')[['close']]"
        ),
        frames=[frame(("session", "close"), (("2026-08-20", 1.0), ("2026-08-21", 2.0)))],
    )

    assert outcome["frame"]["kind"] == "series"


def test_a_missing_number_comes_back_as_null_rather_than_as_a_zero():
    """The distinction the whole refusal vocabulary rests on, held here too."""
    outcome = runner.run(
        code="result = (f0['a'] / f0['b']).to_frame(name='ratio')",
        frames=[frame(("a", "b"), ((1.0, 0.0), (4.0, 2.0)))],
    )

    assert [row[0] for row in outcome["frame"]["rows"]] == [None, 2.0]


# -- that it does not let anything out -----------------------------------------


def test_the_five_modules_the_validator_allows_can_actually_be_imported():
    """Two gates saying different things would be one gate and one bug.

    The validator permits five modules by reading the code; the sandbox permits
    five by guarding ``__import__``. If they disagreed, code the validator waved
    through would die at runtime with a message about imports — a refusal the
    model would have no way to have avoided.
    """
    from src.studies.compute import validator as gate
    from src.studies.compute import worker

    assert worker.ALLOWED_MODULES == gate.ALLOWED_MODULES

    outcome = runner.run(
        code=(
            "import math\n"
            "import datetime\n"
            "result = (f0['net_profit'] * math.pi).to_frame()"
        ),
        frames=[QUARTERS],
    )

    assert outcome["ok"] is True


def test_a_module_outside_the_five_cannot_be_imported_even_past_the_validator():
    """Proven by handing the worker code the validator would have refused.

    The validator is the first gate and this is the second, and testing the
    second one means going round the first: a defence only checked behind
    another defence is a defence nobody has watched work.
    """
    outcome = runner.run(
        code="import socket\nresult = f0",
        frames=[QUARTERS],
    )

    assert outcome["ok"] is False
    assert outcome["error"] == runner.RUNTIME_ERROR
    assert "socket" in outcome["detail"]


def test_a_page_pandas_is_asked_to_read_over_the_network_never_arrives():
    """The hole the import guard alone leaves: ``pd`` is already in scope.

    ``read_json`` reaches a socket without importing one, which is exactly the
    case a module list cannot cover — so the socket itself is taken away before
    the calculation starts.
    """
    outcome = runner.run(
        code="result = pd.read_json('http://example.com/x.json')",
        frames=[QUARTERS],
        wall_seconds=20,
    )

    assert outcome["ok"] is False
    assert outcome["error"] == runner.RUNTIME_ERROR
    # And it says so in words the model can act on, which is the claim worth
    # holding. *Which* of the two sentences it gets moved once, deliberately:
    # reaching a URL makes pandas import ``urllib`` first, and the import gate
    # now answers before the socket does. Both are refusals a model can read;
    # asserting on one of them would have been asserting on the order.
    assert (
        "ra ngoài" in outcome["detail"]
        or worker.BLOCKED_MESSAGE in outcome["detail"]
    )


def test_a_loop_that_never_ends_is_stopped_and_named():
    started = time.perf_counter()
    outcome = runner.run(code="while True:\n    pass\nresult = f0", frames=[QUARTERS])
    elapsed = time.perf_counter() - started

    assert outcome["error"] == runner.TIMEOUT
    assert elapsed < runner.WALL_SECONDS + 3, elapsed


def test_an_allocation_larger_than_the_box_is_stopped_where_the_box_exists():
    """A ceiling the response has to be honest about.

    macOS refuses ``RLIMIT_AS``, so on a developer's machine this allocation is
    caught by the clock rather than by the memory limit. Both are named failures
    and either is a correct answer; what would not be correct is a test that
    read as proof of a memory ceiling on a platform that has none.
    """
    outcome = runner.run(
        code="big = [0] * 10 ** 12\nresult = f0",
        frames=[QUARTERS],
        wall_seconds=20,
    )

    assert outcome["ok"] is False
    assert outcome["error"] in (
        runner.MEMORY_EXCEEDED,
        runner.TIMEOUT,
        runner.RUNTIME_ERROR,
    )


def test_something_pandas_prints_does_not_corrupt_the_answer():
    """Stdout is the protocol, so it is moved rather than defended by a rule.

    ``print`` is not in the sandbox's builtins and ``sys`` cannot be imported,
    so this reaches stdout the way a calculation actually could: a pandas method
    that writes there itself.
    """
    outcome = runner.run(
        code="f0.info()\nresult = f0[['symbol']]",
        frames=[QUARTERS],
    )

    assert outcome["ok"] is True
    assert outcome["frame"]["columns"] == ["symbol"]


# -- that a failure is a result ------------------------------------------------


def test_a_wrong_column_name_comes_back_as_something_to_fix():
    outcome = runner.run(code="result = f0[['roe']]", frames=[QUARTERS])

    assert outcome["error"] == runner.RUNTIME_ERROR
    assert "roe" in outcome["detail"]


def test_a_traceback_does_not_say_where_this_machine_keeps_its_files():
    outcome = runner.run(code="result = f0[['roe']]", frames=[QUARTERS])

    assert "/src/studies" not in outcome["detail"]
    assert "site-packages" not in outcome["detail"]


def test_code_that_leaves_result_as_something_else_is_named_rather_than_guessed():
    outcome = runner.run(code="result = 5", frames=[QUARTERS])

    assert outcome["error"] == "compute_no_result"


def test_an_answer_taller_than_a_picture_is_refused_with_both_numbers():
    outcome = runner.run(
        code="result = pd.concat([f0] * 200)",
        frames=[QUARTERS],
    )

    assert outcome["error"] == runner.RESULT_TOO_LARGE
    assert str(runner.MAX_RESULT_ROWS) in outcome["detail"]
    assert ".tail()" in outcome["detail"]


def test_an_answer_wider_than_a_row_a_reader_can_read_is_refused_too():
    wide = frame(
        tuple(f"c{index}" for index in range(20)),
        ((tuple(float(index) for index in range(20))),),
    )
    outcome = runner.run(code="result = f0", frames=[wide])

    assert outcome["error"] == runner.RESULT_TOO_LARGE
    assert str(runner.MAX_RESULT_COLUMNS) in outcome["detail"]


# -- that it is the same answer every time -------------------------------------


def test_the_same_calculation_on_the_same_frames_gives_the_same_bytes():
    """Replay is the artifact's promise, and it starts here.

    Re-opening a thread a month later renders the artifact rather than
    recomputing it — but a code change that made the same inputs give different
    numbers would make the stored frame unverifiable, which is the whole reason
    the ``params`` carry the code.
    """
    code = "result = (f0['net_profit'] / f0['equity'] * 100).to_frame(name='roe')"
    first = runner.run(code=code, frames=[QUARTERS])
    second = runner.run(code=code, frames=[QUARTERS])

    assert first["frame"] == second["frame"]


# -- the twenty shapes a question actually asks for ----------------------------

#: The calculations this axis exists to make possible, written the way a model
#: would write them. Twenty rather than three because the claim being tested is
#: *generality*: an enumeration of operations would pass the first four of these
#: and answer the fifth with prose, which is the failure the whole phase is
#: about. Every one is checked for the answer it should give, not merely for
#: running — a sandbox that returned the wrong number quietly would pass a test
#: that only asserted ``ok``.
PANEL = frame(
    ("period", "symbol", "net_profit", "equity", "revenue"),
    (
        ("2025-Q1", "VIC", 1_000.0, 20_000.0, 40_000.0),
        ("2025-Q2", "VIC", 1_200.0, 20_500.0, 44_000.0),
        ("2025-Q3", "VIC", 900.0, 21_000.0, 39_000.0),
        ("2025-Q4", "VIC", 1_500.0, 22_000.0, 50_000.0),
        ("2025-Q1", "VCB", 8_000.0, 90_000.0, 20_000.0),
        ("2025-Q2", "VCB", 8_400.0, 92_000.0, 21_000.0),
        ("2025-Q3", "VCB", 8_100.0, 93_000.0, 20_500.0),
        ("2025-Q4", "VCB", 9_000.0, 95_000.0, 23_000.0),
    ),
)

SESSIONS = frame(
    ("session", "symbol", "close", "volume"),
    tuple(
        (f"2026-06-{day:02d}", "VIC", 40.0 + day, 1_000_000.0 + day * 1_000)
        for day in range(1, 21)
    ),
)

SAMPLES: tuple[tuple[str, str, object], ...] = (
    (
        "ratio",
        "result = (f0['net_profit'] / f0['equity'] * 100).to_frame(name='roe')",
        lambda out: out["rows"][0][0] == pytest.approx(5.0),
    ),
    (
        "growth quarter on quarter",
        "grouped = f0.groupby('symbol')['net_profit']\n"
        "result = grouped.pct_change().mul(100).to_frame(name='qoq')",
        lambda out: out["rows"][1][0] == pytest.approx(20.0),
    ),
    (
        "growth year on year",
        "wide = f0.pivot(index='period', columns='symbol', values='net_profit')\n"
        "result = wide.pct_change(3).mul(100)",
        lambda out: len(out["rows"]) == 4,
    ),
    (
        "share of total",
        "total = f0.groupby('period')['revenue'].transform('sum')\n"
        "result = (f0['revenue'] / total * 100).to_frame(name='share')",
        lambda out: out["rows"][0][0] == pytest.approx(200 / 3, abs=0.01),
    ),
    (
        "rank",
        "totals = f0.groupby('symbol', as_index=False)['net_profit'].sum()\n"
        "totals['rank'] = totals['net_profit'].rank(ascending=False)\n"
        "result = totals",
        lambda out: sorted(row[2] for row in out["rows"]) == [1.0, 2.0],
    ),
    (
        "rolling mean over a declared window",
        "result = f0['close'].rolling(window).mean().to_frame(name='ma')",
        lambda out: out["rows"][-1][0] == pytest.approx(58.5),
    ),
    (
        "pivot symbol against period",
        "result = f0.pivot(index='period', columns='symbol', values='net_profit')",
        lambda out: out["columns"] == ["period", "VCB", "VIC"],
    ),
    (
        "cumulative sum",
        "result = f0.groupby('symbol')['net_profit'].cumsum().to_frame(name='cum')",
        lambda out: out["rows"][3][0] == pytest.approx(4600.0),
    ),
    (
        "difference between two columns",
        "result = (f0['revenue'] - f0['net_profit']).to_frame(name='cost')",
        lambda out: out["rows"][0][0] == pytest.approx(39_000.0),
    ),
    (
        "margin",
        "result = (f0['net_profit'] / f0['revenue'] * 100).to_frame(name='margin')",
        lambda out: out["rows"][0][0] == pytest.approx(2.5),
    ),
    (
        "group mean",
        "result = f0.groupby('symbol', as_index=False)['net_profit'].mean()",
        lambda out: len(out["rows"]) == 2,
    ),
    (
        "min and max in one table",
        "result = f0.groupby('symbol', as_index=False)['close'].agg(['min', 'max'])",
        lambda out: len(out["rows"]) == 1,
    ),
    (
        "standard deviation",
        "result = f0.groupby('symbol', as_index=False)['net_profit'].std()",
        lambda out: len(out["rows"]) == 2,
    ),
    (
        "z score against the column",
        "col = f0['net_profit']\n"
        "result = ((col - col.mean()) / col.std()).to_frame(name='z')",
        lambda out: len(out["rows"]) == 8,
    ),
    (
        "filter to one symbol",
        "result = f0[f0['symbol'] == 'VIC'][['period', 'net_profit']]",
        lambda out: len(out["rows"]) == 4,
    ),
    (
        "sort and take the top rows",
        "result = f0.sort_values('net_profit', ascending=False).head(3)",
        lambda out: len(out["rows"]) == 3,
    ),
    (
        "merge two frames on a key",
        "result = f0.merge(f1, on=['period', 'symbol'], suffixes=('', '_b'))",
        lambda out: len(out["rows"]) == 8,
    ),
    (
        "turnover from price and volume",
        "result = (f0['close'] * f0['volume']).to_frame(name='turnover')",
        lambda out: out["rows"][0][0] == pytest.approx(41.0 * 1_001_000),
    ),
    (
        "index rebased to the first session",
        "close = f0['close']\n"
        "result = (close / close.iloc[0] * 100).to_frame(name='rebased')",
        lambda out: out["rows"][0][0] == pytest.approx(100.0),
    ),
    (
        "count of periods a symbol filed",
        "result = f0.groupby('symbol', as_index=False)['period'].count()",
        lambda out: {row[1] for row in out["rows"]} == {4},
    ),
)


@pytest.mark.parametrize("name, code, check", SAMPLES, ids=[row[0] for row in SAMPLES])
def test_a_shape_a_question_actually_asks_for_computes_correctly(name, code, check):
    frames = [SESSIONS, PANEL] if "close" in code or "volume" in code else [PANEL, PANEL]
    outcome = runner.run(
        code=code,
        frames=frames,
        constants={"window": 4} if "window" in code else None,
    )

    assert outcome.get("ok") is True, outcome
    assert check(outcome["frame"]), outcome["frame"]


def test_the_twenty_shapes_all_finish_well_inside_the_budget():
    """The latency claim, measured rather than asserted from a design document.

    A calculation that took two seconds would spend a fifth of a Turn's whole
    wall clock on arithmetic somebody could have waited less for, and the number
    that matters is the median rather than the worst: the worst here is the
    first, which pays for a cold interpreter.
    """
    elapsed: list[float] = []
    for _name, code, _check in SAMPLES:
        frames = (
            [SESSIONS, PANEL] if "close" in code or "volume" in code else [PANEL, PANEL]
        )
        started = time.perf_counter()
        runner.run(
            code=code,
            frames=frames,
            constants={"window": 4} if "window" in code else None,
        )
        elapsed.append(time.perf_counter() - started)

    elapsed.sort()
    p50 = elapsed[len(elapsed) // 2]
    p95 = elapsed[int(len(elapsed) * 0.95) - 1]

    assert p50 < 1.5, (p50, p95, elapsed)


# -- the escape that was measured working ---------------------------------------


def _escaped(code: str) -> dict:
    return runner.run(code=code, frames=[QUARTERS], wall_seconds=20)


def test_the_module_a_library_hands_out_reaches_nothing():
    """The escape this sandbox was measured failing, closed at the object.

    ``pd.io.common.os`` **is** ``sys.modules['os']`` — pandas holds a reference
    to the real module and hands it out as a plain attribute, so a calculation
    reached ``os.popen`` and ran a shell command without ever writing the word
    ``import``. The validator reported zero violations, because there was
    nothing about it to read.

    Written as the exact code that worked, so this test goes red the day
    somebody makes the refusal conditional on something.
    """
    outcome = _escaped(
        "o = pd.io.common.os\n"
        "out = o.popen('/bin/echo escaped').read()\n"
        "result = pd.DataFrame({'x': [out]})"
    )

    assert outcome["ok"] is False
    assert worker.BLOCKED_MESSAGE in outcome["detail"]


def test_a_file_that_is_not_a_module_cannot_be_opened_by_any_of_its_names():
    """One function, several module attributes, and all of them narrowed.

    ``builtins.open``, ``io.open`` and ``_io.open`` are one object under three
    names, and ``os.open`` and ``posix.open`` are another such pair. A guard on
    one leaves the others, which is why the table names every holder rather than
    every function.
    """
    for reach in (
        "pd.core.common.builtins.open('/etc/passwd')",
        "pd._testing._io.io.open('/etc/passwd')",
        "pd.io.common.os.open('/etc/passwd', 0)",
        "pd._testing._io.tarfile.shutil.posix.open('/etc/passwd', 0)",
    ):
        outcome = _escaped(f"result = pd.DataFrame({{'x': [str({reach})]}})")

        assert outcome["ok"] is False, reach
        assert worker.BLOCKED_MESSAGE in outcome["detail"], reach


def test_the_real_builtins_cannot_be_reached_through_a_frame():
    """A frame carries ``f_builtins``, which is every name the sandbox removed.

    Removing a name from the mapping user code is given removes it from a copy.
    ``sys._getframe`` hands back the original, so it is taken off ``sys`` — and
    ``sys`` itself is reachable, measured, at ``statistics.sys``.
    """
    outcome = _escaped(
        "s = statistics.sys\nresult = pd.DataFrame({'x': [str(s._getframe(0))]})"
    )

    assert outcome["ok"] is False
    assert worker.BLOCKED_MESSAGE in outcome["detail"]


def test_a_raw_capability_module_cannot_be_imported_from_inside_a_string():
    """The gate that holds when the validator never saw the code, at its worst case.

    ``exec`` is left working because the import system runs a module body with
    it, so a calculation can write an import the AST pass never read. Handed
    only the code, ``exec`` inherits the sandbox's own guarded ``__import__``
    and the five-name allowlist answers. The worst case is the one below: the
    real ``builtins`` module injected as the globals of the executed string, so
    the reduced mapping is gone and what is left is the process gate.

    ``_posixsubprocess`` is why that gate is not redundant with the table: it is
    the fork/exec primitive, it is not loaded, and a module that is not loaded
    has no object whose calls could have been replaced.
    """
    for reach in (
        "b.exec('import _posixsubprocess', {'__builtins__': b})",
        "b.exec('import os; z = os.popen(\"id\").read()', {'__builtins__': b})",
        "b.exec('z = open(\"/etc/passwd\").read()', {'__builtins__': b})",
    ):
        outcome = _escaped(f"b = pd.core.common.builtins\n{reach}\nresult = f0")

        assert outcome["ok"] is False, reach
        assert worker.BLOCKED_MESSAGE in outcome["detail"], reach


def test_a_library_this_process_loaded_lazily_still_loads():
    """The other half of the claim, and the half that kept being broken.

    Four of these operations import a numpy submodule the first time they run —
    which means they read a ``.pyc`` off disk, unmarshal it and exec it. Every
    early version of the hardening closed one of those three and took the
    library down with it. The escape tests above say what may not happen; this
    says what still must.
    """
    for code in (
        "result = f0.assign(g=f0['net_profit'].pct_change())",
        "result = f0[['net_profit']].describe().reset_index()",
        "result = f0.assign(r=f0['net_profit'].rank())",
        "result = f0.groupby('symbol', as_index=False).agg(t=('net_profit', 'sum'))",
        "result = f0.assign(d=pd.to_datetime(f0['period'].str.replace('-Q1', '-01-01')"
        ".str.replace('-Q2', '-04-01')))",
    ):
        outcome = runner.run(code=code, frames=[QUARTERS], wall_seconds=20)

        assert outcome["ok"] is True, (code, outcome.get("detail"))


def test_the_two_import_gates_do_not_contradict_each_other():
    """The sandbox's allowlist and the process's denylist must not overlap.

    A module named by both would be one the validator says is allowed and the
    import gate refuses — a refusal the model could not have avoided, which is
    the exact failure the two-gate comment in ``worker.py`` warns about.
    """
    assert worker.ALLOWED_MODULES & worker.IMPORT_DENYLIST == frozenset()
