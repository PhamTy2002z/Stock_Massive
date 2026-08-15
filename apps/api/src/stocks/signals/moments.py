"""The two sample moments every cluster in this package needs.

Written once because they were on their way to being written four times. A
sample variance and the standard error of a mean are not interesting arithmetic,
which is exactly why four spellings of them would be four chances to divide by
``n`` where the estimator wanted ``n − 1`` — and the one that got it wrong would
publish a slightly narrow uncertainty on a field whose whole contract is that its
uncertainty is honest.

Nothing here is a substitute for the corrections that live with their own
estimators. Lo's autocorrelation-corrected annualization stays in ``risk``, and
the Newey-West long-run error stays in ``foreign_flow``: both are the point of
the field they serve rather than a shared detail, and folding them in here would
make one module the owner of three different papers' arguments.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def sample_variance(values: Sequence[float]) -> float | None:
    """The mean-adjusted sample variance, or nothing below two observations.

    ``n − 1`` in the divisor, which is what makes it the sample variance rather
    than the population one: a single observation has no dispersion to estimate
    and the answer is ``None``, not zero.
    """
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return sum((item - mean) ** 2 for item in values) / (len(values) - 1)


def mean_standard_error(values: Sequence[float]) -> float | None:
    """How far the mean of these observations would move if they were drawn again.

    ``s/√n``, which assumes the observations are independent. Where they are not
    — a persistent flow, an autocorrelated return — the estimator that reads them
    carries its own correction and does not call this.
    """
    variance = sample_variance(values)
    if variance is None:
        return None
    return math.sqrt(variance / len(values))
