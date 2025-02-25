"""
PFLOTRAN implementation of the render stage.
This stage generates all necessary input files to run PFLOTRAN simulations, i.e., the `mesh.uge` file, boundary `.ex`
files, the `pflotran.in` file and also any `.h5` files.
"""

import logging
import pathlib
import warnings

import jinja2
import numpy as np
from h5py import File

# This supresses unwanted output as the library tries to write to its installation directory
with warnings.catch_warnings(action="ignore"):
    from numpydantic import NDArray

from ...data_structures import HeatPump, State, ValueXYZ
from ...variation_stage.vary_perlin import create_const_field
from .pflotran_generate_mesh import write_mesh_and_border_files


def render_stage(state: State):
    """
    Render all files needed for pflotran to run.
    This means, `write_mesh_and_border_files`, rendering the pflotran.in file and rendering the permeability field with
    `save_vary_field`.
    """

    write_mesh_and_border_files(state, state.general.output_directory)

    LoggingUndefined = jinja2.make_logging_undefined(logger=logging.getLogger())
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(pathlib.Path(__file__).parent / "templates"), undefined=LoggingUndefined
    )
    template = env.get_template("pflotran.in.j2")

    for index, datapoint in enumerate(state.datapoints):
        datapoint_dir = state.general.output_directory / f"datapoint-{index}"

        # Ensure pressure_gradient is x, y, z
        pressure_gradient = datapoint.data["pressure_gradient"]
        if isinstance(pressure_gradient.value, float):
            pressure_gradient.value = ValueXYZ(x=0, y=pressure_gradient.value, z=0)

        # Handle permeability
        permeability = datapoint.data["permeability"]

        # Is the permeability already a 3d field? If not, create one
        if isinstance(permeability.value, float | NDArray):  # pyright: ignore[reportArgumentType]
            permeability.value = create_const_field(state, permeability.value)  # pyright: ignore[reportArgumentType]

        save_vary_field(
            datapoint_dir / "permeability_field.h5",
            state.general.number_cells,
            permeability.value,
            permeability.name,
        )

        heatpumps = [{name: d.value} for name, d in datapoint.data.items() if isinstance(d.value, HeatPump)]

        values = datapoint.data
        values["heatpumps"] = heatpumps  # type: ignore
        values["time_to_simulate"] = state.general.time_to_simulate  # type: ignore

        with open(f"{datapoint_dir}/pflotran.in", "w") as file:
            file.write(template.render(values))
            logging.debug("Rendered pflotran-%s.in", index)


def save_vary_field(filename, number_cells, cells, parameter_name: str = "permeability"):
    """
    Writes the `.h5` field file for the given `parameter_name`.
    The values for the file were calculated during the variation stage.
    """

    n = number_cells[0] * number_cells[1] * number_cells[2]
    # create integer array for cell ids
    iarray = np.arange(n, dtype="i4")
    iarray[:] += 1  # convert to 1-based
    cells_array_flatten = cells.reshape(n, order="F")

    with File(filename, mode="w") as h5file:
        h5file.create_dataset("Cell Ids", data=iarray)
        h5file.create_dataset(parameter_name.title(), data=cells_array_flatten)

    logging.info(f"Created a {parameter_name}-field")
