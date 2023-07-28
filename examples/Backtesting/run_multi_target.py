### Example for full simulation loop using the multi target mode for custom analytic functions

"""
This example shows how to use a multi target objective for a custom analytic function.
It uses a desirability value to handle several targets.
"""

# This example assumes basic familiarty with BayBE, custom test functions and multiple targets.
# For further details, we thus refer to
# - [`baybe_object`](./../Basics/baybe_object.md) for a more general and basic example,
# - [`run_custom_analytical`](./run_custom_analytical.md) for custom test functions, and
# - [`desirability`](./../Multi_Target/desirability.md) for multiple targets.

#### Necessary imports for this example

from typing import Tuple

import numpy as np
from baybe.core import BayBE
from baybe.parameters import NumericDiscrete
from baybe.searchspace import SearchSpace
from baybe.simulation import simulate_scenarios
from baybe.targets import NumericalTarget, Objective

### Parameters for a full simulation loop

# For the full simulation, we need to define some additional parameters.
# These are the number of Monte Carlo runs and the number of experiments to be conducted per run.

N_MC_ITERATIONS = 2
N_EXP_ITERATIONS = 4

### Defining the test function


# See [`run_custom_analytical`](./run_custom_analytical.md) for details
def sum_of_squares(*x: float) -> Tuple[float, float]:
    """
    Calculates the sum of squares.
    """
    res = 0
    for y in x:
        res += y**2
    return res, 2 * res**2 - 1


DIMENSION = 4
BOUNDS = [(-2, 2), (-2, 2), (-2, 2), (-2, 2)]

### Creating the searchspace and the objective

#### Creating the searchspace

# In this example, we construct a purely discrete space with 10 points per dimension.
parameters = [
    NumericDiscrete(
        name=f"x_{k+1}",
        values=list(np.linspace(*BOUNDS[k], 10)),
        tolerance=0.01,
    )
    for k in range(DIMENSION)
]

searchspace = SearchSpace.from_product(parameters=parameters)


#### Creating multiple target object

# The multi target mode is handled when creating the objective object.
# Thus we first need to define the different targets.
# We use two targets here.
# The first target is maximized and the second target is minimized during the optimization process.
Target_1 = NumericalTarget(
    name="Target_1", mode="MAX", bounds=(0, 100), bounds_transform_func="LINEAR"
)
Target_2 = NumericalTarget(
    name="Target_2", mode="MIN", bounds=(0, 100), bounds_transform_func="LINEAR"
)


#### Creating the objective object

# We collect the two targets in a list and use this list to construct the objective.

targets = [Target_1, Target_2]

objective = Objective(
    mode="DESIRABILITY",
    targets=targets,
    weights=[20, 30],
    combine_func="MEAN",
)


### Constructing a BayBE object and performing the simulation loop

baybe_obj = BayBE(searchspace=searchspace, objective=objective)

# We can now use the `simulate_scenarios` function to simulate a full experiment.
scenarios = {"BayBE": baybe_obj}

results = simulate_scenarios(
    scenarios=scenarios,
    batch_quantity=2,
    n_exp_iterations=4,
    n_mc_iterations=2,
    lookup=sum_of_squares,
)

print(results)
