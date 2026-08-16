# Eval Reports

One file per Eval Battery run, written by `make eval` and named
`<date>-<prompt_version>.md`. **Commit them.** The baseline is read from
`eval_run` in SQL, but the reports are what give it a diffable history — and the
verbatim answers a human rubric scored live here and nowhere else.

A `smoke` run's report carries its mode and a short run id in the filename. It
is non-gating, it can never be a baseline, and it does not belong on a pull
request.

Which pull requests must carry a report, and what a `baseline_reset` means for
one that does: `docs/agents/eval-battery.md`.
