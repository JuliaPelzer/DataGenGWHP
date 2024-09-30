from typing import Any

import noise
import numpy as np
from numpy.typing import NDArray

from ..config import Config, Distribution, Parameter, ParameterValueMinMax, ParameterValuePerlin


def make_perlin_grid(
    aimed_min: float,
    aimed_max: float,
    config: Config,
    offset: NDArray[np.float64],
    freq: list[float],
) -> NDArray[np.floating[Any]]:
    grid_dimensions: list[int] = config.general.number_cells

    # adapted by Manuel Hirche

    # We sample the permeability from 3 dimensional perlin noise that extends indefinetly.
    # To introduce randomness the starting point of our sampling is drawn from a uniform
    # distribution. From there we are moving a multiple of our simulation area for every
    # sample to get non-overlapping fields. The simulation area is scaled to a unit cube so
    # conveniently we can move by 1 in x directon (in this direction the scaled area
    # will be << 1)

    # Scale the simulation area down into a unit cube
    simulation_area_max = max(grid_dimensions)
    scale_x = grid_dimensions[0] / simulation_area_max
    scale_y = grid_dimensions[1] / simulation_area_max
    scale_z = grid_dimensions[2] / simulation_area_max

    values = np.zeros((grid_dimensions[0], grid_dimensions[1], grid_dimensions[2]))
    for i in range(0, grid_dimensions[0]):
        for j in range(0, grid_dimensions[1]):
            for k in range(0, grid_dimensions[2]):
                x = i / grid_dimensions[0] * scale_x + offset[0]
                y = j / grid_dimensions[1] * scale_y + offset[1]
                z = k / grid_dimensions[2] * scale_z + offset[2]

                x = x * freq[0]
                y = y * freq[1]
                z = z * freq[2]

                values[i, j, k] = noise.pnoise3(x, y, z)

    # scale to intended range
    current_min = np.min(values)
    current_max = np.max(values)

    values = (values - current_min) / (current_max - current_min)
    values = values * (aimed_max - aimed_min) + aimed_min

    return values


def create_perlin_field(config: Config, parameter: Parameter):
    base_offset = config.get_rng().random(3) * 4242

    if not isinstance(parameter.value, ParameterValuePerlin):
        raise ValueError()

    freq_factor = parameter.value.frequency

    vary_min = parameter.value.min
    vary_max = parameter.value.max

    if parameter.distribution == Distribution.LOG:
        vary_min = np.log10(vary_min)
        vary_max = np.log10(vary_max)

    cells = make_perlin_grid(
        vary_min,
        vary_max,
        config,
        base_offset,
        freq_factor,
    )

    if parameter.distribution == Distribution.LOG:
        cells = 10**cells

    if parameter.name == "hydraulic_head":
        cells = calc_pressure_from_gradient_field(cells, config, parameter)

    return cells


def create_const_field(config: Config, value: float):
    # TODO think about pressure
    return np.full(config.general.number_cells, value)


def calc_pressure_from_gradient_field(
    gradient_field: NDArray[np.float64], config: Config, parameter: Parameter
) -> NDArray[np.float64]:
    # XXX: is this function correctly implemented?

    value = parameter.value
    assert isinstance(value, ParameterValueMinMax)

    # scale pressure field to min and max values from config
    current_min = np.min(gradient_field)
    current_max = np.max(gradient_field)

    new_min = value.min
    new_max = value.max

    gradient_field = (gradient_field - current_min) / (current_max - current_min) * (new_max - new_min) + new_min

    reference = 101325  # Standard atmosphere pressure in Pa
    resolution = config.general.cell_resolution

    pressure_field = np.zeros_like(gradient_field)
    pressure_field[:, 0] = reference
    for i in range(1, pressure_field.shape[1]):
        pressure_field[:, i] = pressure_field[:, i - 1] + gradient_field[:, i] * resolution[1] * 1000
    pressure_field = pressure_field[::-1]

    # for i in range(1, pressure_field.shape[0]):
    #     pressure_field[i,:] = (pressure_field[i-1,:] + gradient_field[i,:] * resolution[0] + pressure_field[i,:])/2
    # pressure_field = gradient_field * resolution[1] + reference

    return pressure_field
