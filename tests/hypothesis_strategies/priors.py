"""Hypothesis strategies for priors."""

import hypothesis.strategies as st

from baybe.kernels.priors import (
    GammaPrior,
    HalfCauchyPrior,
    HalfNormalPrior,
    LogNormalPrior,
    NormalPrior,
    SmoothedBoxPrior,
)

from .utils import intervals

gamma_priors = st.builds(
    GammaPrior,
    st.floats(min_value=0, exclude_min=True),
    st.floats(min_value=0, exclude_min=True),
)
"""A strategy that generates Gamma priors."""

half_cauchy_priors = st.builds(
    HalfCauchyPrior,
    st.floats(min_value=0, exclude_min=True),
)
"""A strategy that generates Half-Cauchy priors."""

normal_priors = st.builds(
    NormalPrior,
    st.floats(allow_nan=False, allow_infinity=False),
    st.floats(min_value=0, exclude_min=True),
)
"""A strategy that generates Normal priors."""

half_normal_priors = st.builds(
    HalfNormalPrior,
    st.floats(min_value=0, exclude_min=True),
)
"""A strategy that generates Half-Normal priors."""

log_normal_priors = st.builds(
    LogNormalPrior,
    st.floats(allow_nan=False, allow_infinity=False),
    st.floats(min_value=0, exclude_min=True),
)
"""A strategy that generates Log-Normal priors."""


@st.composite
def _smoothed_box_priors(draw: st.DrawFn):
    """A strategy that generates Smoothed-Box priors."""
    interval = draw(intervals(exclude_half_bounded=True, exclude_fully_unbounded=True))
    sigma = draw(
        st.floats(min_value=0, exclude_min=True),
    )

    return SmoothedBoxPrior(*interval.to_tuple(), sigma)


smoothed_box_priors = _smoothed_box_priors()

priors = st.one_of(
    [
        gamma_priors,
        half_cauchy_priors,
        half_normal_priors,
        log_normal_priors,
        normal_priors,
        smoothed_box_priors,
    ]
)
"""A strategy that generates priors."""
