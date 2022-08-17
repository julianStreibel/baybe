"""
Functionality for different type of targets.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import partial
from typing import ClassVar, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Extra, validator

from .utils import check_if_in, geom_mean
from .utils.boundtransforms import bound_bell, bound_lmu_linear, bound_lu_linear

log = logging.getLogger(__name__)


def _validate_bounds(bounds: Optional[Tuple[float, float]] = None):
    """
    Shortcut validator for bounds. Currently only either no bounds (= set to None) or
    completely finite bounds (= set to a list of two finite floats) are supported
    """
    # IMPROVE could also include half-way bounds but that doesnt work for the
    #  desirability approach
    if bounds is not None:
        if (not isinstance(bounds, tuple)) or (len(bounds) != 2):
            raise TypeError(f"Bounds were {bounds} but must be a 2-tuple")

        if not all(np.isfinite(bounds)):
            raise TypeError(
                f"Bounds were {bounds} but need to contain finite float numbers. If you"
                f" want no bounds set bounds to None."
            )

        if bounds[1] <= bounds[0]:
            raise ValueError(
                f"The upper bound must be greater than the lower bound. Encountered "
                f"for bounds {bounds}."
            )

    return bounds


class Objective(BaseModel, extra=Extra.forbid):
    """Class for managing optimization objectives."""

    mode: Literal["SINGLE", "MULTI", "DESIRABILITY"]
    targets: List[dict]
    weights: Optional[List[float]] = None
    combine_func: Optional[Literal["MEAN", "GEOM_MEAN"]] = "GEOM_MEAN"

    @validator("targets", always=True)
    def validate_targets(cls, targets, values):
        """
        Validates targets depending on the objective mode
        """
        if (values["mode"] == "SINGLE") and (len(targets) != 1):
            raise ValueError(
                "For objective mode SINGLE you must specify exactly one target."
            )
        if (values["mode"] == "MULTI") and (len(targets) <= 1):
            raise ValueError(
                "For objective mode MULTI you must specify more than one target."
            )
        if values["mode"] == "DESIRABILITY":
            for target in targets:
                if ("bounds" not in target) or (target["bounds"] is None):
                    # FIXME exceptions raised in here does not seem to be triggered
                    raise ValueError(
                        "In DESIRABILITY mode for multiple targets, each target must"
                        " have bounds defined."
                    )

        return targets

    @validator("weights", always=True)
    def validate_weights(cls, weights, values):
        """
        Validates target weights
        """
        numtargets = len(values["targets"])
        if weights is None:
            weights = list(100 * np.ones(numtargets) / np.sum(numtargets))

        if len(weights) != numtargets:
            raise ValueError(
                f"Weights list for your objective has {len(weights)} values, but you "
                f"defined {numtargets} targets."
            )

        # Normalize to sum = 100
        weights = [100.0 * w / np.sum(weights) for w in weights]

        return weights

    def transform(self, data: pd.DataFrame, targets: List[Target]) -> pd.DataFrame:
        """
        Transforms targets in experimental representation to a computational
        representation

        Parameters
        ----------
        data: pd.DataFrame
            The data to be transformed. Can must contain all target values, can
            contain more columns
        targets
            A list of BayBE targets
        Returns
        -------
        pd.DataFrame
            A dataframe with the targets in computational representation, Columns will
            be the same as input, except for the DESIRABILITY objective mode
        """
        # Perform transformations that are required independent of the mode
        transformed = data[[t.name for t in targets]].copy()
        for target in targets:
            transformed[target.name] = target.transform(data[target.name])

        # In desirability mode the targets are additionally combined further into one
        if self.mode == "DESIRABILITY":
            if self.combine_func == "GEOM_MEAN":
                func = geom_mean
            elif self.combine_func == "MEAN":
                func = partial(np.average, axis=1)
            else:
                raise ValueError(
                    f"The specified averaging function {self.combine_func} is not know"
                )

            vals = func(transformed.values, weights=self.weights)
            transformed = pd.DataFrame({"Comp_Target": vals}, index=transformed.index)

        return transformed


class Target(ABC, BaseModel, extra=Extra.forbid):
    """
    Abstract base class for all target variables. Stores information about the type,
    range, transformations, etc.
    """

    # class variables
    type: ClassVar[str]
    SUBCLASSES: ClassVar[Dict[str, Target]] = {}

    # object variables
    name: str

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.SUBCLASSES[cls.type] = cls

    @classmethod
    def create(cls, config: dict) -> Target:
        """Creates a new target object matching the given specifications."""
        config = config.copy()
        param_type = config.pop("type")
        check_if_in(param_type, list(Target.SUBCLASSES.keys()))
        return cls.SUBCLASSES[param_type](**config)

    @abstractmethod
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Creates a new target representation matching the given specifications."""


class NumericalTarget(Target):
    """
    Class for numerical targets.
    """

    type = "NUM"

    mode: Literal["MIN", "MAX", "MATCH"]
    bounds: Optional[Tuple[float, float]] = None
    bounds_transform_func: Optional[str] = None

    _bound_transform_funcs = {
        "luLINEAR": bound_lu_linear,
        "lmuLINEAR": bound_lmu_linear,
        "BELL": bound_bell,
    }

    _valid_transforms = {
        "MAX": ["luLINEAR"],
        "MIN": ["luLINEAR"],
        "MATCH": ["lmuLINEAR", "BELL"],
    }

    _validated_bounds = validator("bounds", allow_reuse=True)(_validate_bounds)

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms data to the computational representation. The transformation depends
        on the target mode, e.g. minimization, maximization, matching, multi-target etc.

        Parameters
        ----------
        data : pd.DataFrame
            The data to be transformed.

        Returns
        -------
        pd.DataFrame
            The transformed data frame
        """

        transformed = data.copy()
        if self.mode == "MAX":
            if self.bounds is not None:
                if self.bounds_transform_func is None:
                    log.warning(
                        "The bound transform function for target %s in mode %s"
                        " has not been specified. Setting the bound transform "
                        "function to %s",
                        self.name,
                        self.mode,
                        self._valid_transforms[self.mode][0],
                    )
                    self.bounds_transform_func = self._valid_transforms[self.mode][0]
                if self.bounds_transform_func not in self._valid_transforms[self.mode]:
                    raise ValueError(
                        f"You specified bounds for target {self.name}, but your "
                        f"specified bound transform function "
                        f"{self.bounds_transform_func} is not compatible with the "
                        f"target mode {self.mode}. It must be one of "
                        f"{self._valid_transforms[self.mode]}."
                    )
                transformed = self._bound_transform_funcs[self.bounds_transform_func](
                    transformed,
                    l=self.bounds[0],  # noqa: E741
                    u=self.bounds[1],  # noqa: E741
                    bMin=False,  # noqa: E741
                )
            # if in MAX mode without bounds no further transformation is needed
        elif self.mode == "MIN":
            if self.bounds is not None:
                if self.bounds_transform_func is None:
                    log.warning(
                        "The bound transform function for target %s in mode %s"
                        " has not been specified. Setting the bound transform "
                        "function to %s",
                        self.name,
                        self.mode,
                        self._valid_transforms[self.mode][0],
                    )
                    self.bounds_transform_func = self._valid_transforms[self.mode][0]
                if self.bounds_transform_func not in self._valid_transforms[self.mode]:
                    raise ValueError(
                        f"You specified bounds for target {self.name}, but your "
                        f"specified bound transform function "
                        f"{self.bounds_transform_func} is not compatible with the "
                        f"target mode {self.mode}. It must be one of "
                        f"{self._valid_transforms[self.mode]}."
                    )
                transformed = self._bound_transform_funcs[self.bounds_transform_func](
                    transformed,
                    l=self.bounds[0],  # noqa: E741
                    u=self.bounds[1],  # noqa: E741
                    bMin=True,  # noqa: E741
                )
            else:
                # If no bounds are given we can simply negate all target values
                transformed = -transformed
        elif self.mode == "MATCH":
            if self.bounds is not None:
                if self.bounds_transform_func is None:
                    log.warning(
                        "The bound transform function for target %s in mode %s"
                        " has not been specified. Setting the bound transform "
                        "function to %s",
                        self.name,
                        self.mode,
                        self._valid_transforms[self.mode][0],
                    )
                    self.bounds_transform_func = self._valid_transforms[self.mode][0]
                if self.bounds_transform_func not in self._valid_transforms[self.mode]:
                    raise ValueError(
                        f"You specified bounds for target {self.name}, but your "
                        f"specified bound transform function "
                        f"{self.bounds_transform_func} is not compatible with the "
                        f"target mode {self.mode}. It must be one of "
                        f"{self._valid_transforms[self.mode]}."
                    )
                transformed = self._bound_transform_funcs[self.bounds_transform_func](
                    transformed, l=self.bounds[0], u=self.bounds[1]  # noqa: E741
                )
            else:
                raise ValueError(
                    f"Target {self.name} is in MATCH mode but no bounds were provided. "
                    "Bounds for MATCH mode are mandatory."
                )
        else:
            raise ValueError(
                f"The specified mode {self.mode} for target {self.name} is invalid"
            )

        return transformed