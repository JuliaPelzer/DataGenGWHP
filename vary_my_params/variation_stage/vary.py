import logging
from copy import deepcopy
from typing import cast

import numpy as np
from numpy.typing import ArrayLike

from vary_my_params.validation_stage.utils import are_duplicate_locations_in_heatpumps

from ..data_structures import (
    Data,
    DataPoint,
    Distribution,
    HeatPump,
    HeatPumps,
    Parameter,
    State,
    ValueMinMax,
    ValuePerlin,
    ValueTimeSeries,
    Vary,
)
from .vary_perlin import create_perlin_field


def copy_parameter(state: State, parameter: Parameter) -> Data:
    """This function simply copies all values from a `Parameter` to a `Data` object without any transformation"""
    if isinstance(parameter.value, HeatPump):
        return vary_heatpump(state, parameter)
    return Data(name=parameter.name, value=deepcopy(parameter.value))


def vary_heatpump(state: State, parameter: Parameter) -> Data:
    hp = deepcopy(parameter.value)
    assert isinstance(hp, HeatPump)

    hp = handle_heatpump_values(state.get_rng(), hp)

    result_location = np.array(hp.location)
    if parameter.vary == Vary.SPACE:
        # This is needed as we need to calculate the heatpump coordinates for pflotran.in
        result_location = generate_heatpump_location(state)
        resolution = state.general.cell_resolution
        result_location = (np.array(result_location) - 1) * resolution + (resolution * 0.5)

    return Data(
        name=parameter.name,
        value=HeatPump(
            location=cast(list[float], result_location),
            injection_temp=hp.injection_temp,
            injection_rate=hp.injection_rate,
        ),
    )


def vary_parameter(state: State, parameter: Parameter, index: int) -> Data:
    """This function does the variation of `Parameter`s. It does so by implementing a large match-case that in turn
    invokes other functions that then work on the `Parameter.value` based on the `Parameter.vary` type.
    """
    assert not isinstance(parameter.value, HeatPumps)
    match parameter.vary:
        case Vary.FIXED:
            data = copy_parameter(state, parameter)

        case Vary.CONST:
            if isinstance(parameter.value, ValueMinMax):
                max = deepcopy(parameter.value.max)
                min = deepcopy(parameter.value.min)

                if parameter.distribution == Distribution.LOG:
                    max = np.log10(max)
                    min = np.log10(min)

                distance = max - min
                step_width = distance / (state.general.number_datapoints - 1)
                value = min + step_width * index

                if parameter.distribution == Distribution.LOG:
                    value = 10**value

                data = Data(
                    name=parameter.name,
                    value=value,
                )
            else:
                logging.error(
                    "No implementation for %s and %s in parameter %s",
                    type(parameter.value),
                    parameter.vary,
                    parameter.name,
                )
                raise NotImplementedError()

        case Vary.SPACE:
            if isinstance(parameter.value, ValuePerlin):
                data = Data(
                    name=parameter.name,
                    value=create_perlin_field(state, parameter),
                )
            elif isinstance(parameter.value, float):
                raise ValueError(
                    f"Parameter {parameter.name} is vary.space and has a float value, "
                    f"it should be set to vary.fixed with a min/max value instead; {parameter}"
                )
            # This should be inside the CONST block, yet it seems to make more sense to users to find it here
            elif isinstance(parameter.value, HeatPump):
                data = vary_heatpump(state, parameter)
            elif isinstance(parameter.value, ValueMinMax):
                raise ValueError(
                    f"Parameter {parameter.name} is vary.space and has min/max values, "
                    f"it should be set to vary.perlin instead; {parameter}"
                )
            else:
                raise NotImplementedError(f"Dont know how to vary {parameter}")

        case _:
            raise ValueError()
    return data


def calculate_hp_coordinates(state: State) -> State:
    """Calculate the coordinates of each heatpump by multiplying with the cell_resolution"""

    for _, hp_data in state.heatpump_parameters.items():
        assert isinstance(hp_data.value, HeatPump)
        if hp_data.value.location is None:
            # This means the heatpump is assigned a random location during vary stage anyway
            continue

        resolution = state.general.cell_resolution

        hp = hp_data.value
        assert isinstance(hp, HeatPump)

        # This is needed as we need to calculate the heatpump coordinates for pflotran.in
        result_location = (np.array(hp.location) - 1) * resolution + (resolution * 0.5)

        hp.location = cast(list[float], result_location.tolist())

    return state


def handle_heatpump_values(rand: np.random.Generator, hp_data: HeatPump) -> HeatPump:
    """Normalize the given value to a `ValueTimeSeries` with values that lay between the given min/max values."""

    assert isinstance(hp_data.injection_temp, ValueTimeSeries)
    assert isinstance(hp_data.injection_rate, ValueTimeSeries)

    for timestep, value in hp_data.injection_temp.values.items():
        # Iterate over each of the heat pumps time value
        if isinstance(value, ValueMinMax):
            # Value is given as min/max
            hp_data.injection_temp.values[timestep] = value.max - (rand.random() * (value.max - value.min))

    for timestep, value in hp_data.injection_rate.values.items():
        # Iterate over each of the heat pumps time value
        if isinstance(value, ValueMinMax):
            # Value is given as min/max
            hp_data.injection_rate.values[timestep] = value.max - (rand.random() * (value.max - value.min))

    return hp_data


def generate_heatpump_location(state: State) -> list[float]:
    random_vector = state.get_rng().random(3)
    random_location = random_vector * cast(np.ndarray, state.general.number_cells)
    return cast(list[float], np.ceil(random_location).tolist())


def generate_heatpumps(state: State) -> State:
    """Generate `HeatPump`s from the given `HeatPumps` parameter. This function will remove all `HeatPumps` from
    `State.heatpump_parameters` and add `HeatPumps.number` `HeatPump`s to the dict. The `HeatPump.injection_temp` and
    `HeatPump.injection_rate` values are simply taken from a random number between the respective min and max values.
    """

    new_heatpumps: dict[str, Parameter] = {}

    # Need to get the explicit heatpumps first, in case of location clashes we can simply draw another random number
    for _, hps in state.heatpump_parameters.items():
        if isinstance(hps.value, HeatPump):
            new_heatpumps[hps.name] = hps
            continue

    for _, hps in state.heatpump_parameters.items():
        if isinstance(hps.value, HeatPump):
            continue

        if not isinstance(hps.value, HeatPumps):
            raise ValueError("There was a non HeatPumps item in heatpump_parameters")

        for index in range(hps.value.number):  # type:ignore
            name = f"{hps.name}_{index}"
            if (state.heatpump_parameters.get(name) is not None) and (new_heatpumps.get(name) is not None):
                msg = f"There is a naming clash for generated heatpump {name}"
                logging.error(msg)
                raise ValueError(msg)

            injection_temp = hps.value.injection_temp
            injection_rate = hps.value.injection_rate

            location = generate_heatpump_location(state)

            heatpump = HeatPump(
                location=cast(list[float], location),
                injection_temp=injection_temp,
                injection_rate=injection_rate,
            )
            logging.debug("Generated HeatPump %s", heatpump)

            heatpumps = cast(list[HeatPump], [param.value for _, param in new_heatpumps.items()])
            heatpumps.append(heatpump)
            while are_duplicate_locations_in_heatpumps(heatpumps):
                # Generate new heatpump location if the one we had is already taken
                # TODO write test for this
                heatpump.location = generate_heatpump_location(state)

            new_heatpumps[name] = Parameter(
                name=name,
                vary=hps.vary,
                value=heatpump,
            )

    for name, value in new_heatpumps.items():
        if isinstance(value, HeatPumps):
            raise ValueError(f"There should be no HeatPumps in the new_heatpumps dict, but {name} is.")

    logging.debug("Old heatpump_parameters: %s", state.heatpump_parameters)
    state.heatpump_parameters = new_heatpumps
    logging.debug("New heatpump_parameters: %s", state.heatpump_parameters)
    return state


def vary_params(state: State) -> State:
    """Calls the `vary_parameter` function for each datapoint sequentially."""

    for datapoint_index in range(state.general.number_datapoints):
        data = {}

        # This syntax merges the hydrogeological_parameters and the heatpump_parameters dicts so we don't have to write
        # two separate for loops
        for _, parameter in (state.hydrogeological_parameters | state.heatpump_parameters).items():
            parameter_data = vary_parameter(state, parameter, datapoint_index)
            data[parameter.name] = parameter_data

        state.datapoints.append(DataPoint(index=datapoint_index, data=data))

    if state.general.shuffle_datapoints:
        state = shuffle_datapoints(state)
        logging.debug("Shuffled datapoints")

    return state


def shuffle_datapoints(state: State) -> State:
    """Shuffles all `Parameter`s randomly in between the different `DataPoint`s. This is needed when e.g. two
    parameters are generated as `Vary.CONST` with `ValueMinMax`, as otherwise they would both have min
    values in the first `DataPoint` and max values in the last one.
    """

    parameters: dict[str, list[Data]] = {}

    parameter_names = list(state.datapoints[0].data)
    for parameter in parameter_names:
        for datapoint in state.datapoints:
            param_list = parameters.get(parameter, [])
            param_list.append(datapoint.data[parameter])
            parameters[parameter] = param_list

        state.get_rng().shuffle(cast(ArrayLike, parameters[parameter]))

    for parameter in parameter_names:
        for index in range(state.general.number_datapoints):
            state.datapoints[index].data[parameter] = parameters[parameter][index]

    return state


def handle_time_based_params(state: State) -> State:
    """Convert specific parameters to time based entries."""

    # Convert heatpumps to time based values
    for _, heatpump in state.heatpump_parameters.items():
        assert isinstance(heatpump.value, HeatPump)
        if not isinstance(heatpump.value.injection_temp, ValueTimeSeries):
            heatpump.value.injection_temp = ValueTimeSeries(values={0: heatpump.value.injection_temp})
        if not isinstance(heatpump.value.injection_rate, ValueTimeSeries):
            heatpump.value.injection_rate = ValueTimeSeries(values={0: heatpump.value.injection_rate})

    return state


def calculate_frequencies(state: State) -> State:
    """For every `Parameter` that has a value of `ValuePerlin` type, calculate the frequency value if
    `ValueMinMax` is given."""

    # Convert heatpumps to time based values
    for _, parameter in (state.hydrogeological_parameters | state.heatpump_parameters).items():
        if not isinstance(parameter.value, ValuePerlin):
            continue

        if not isinstance(parameter.value.frequency, ValueMinMax):
            continue

        rand = state.get_rng()

        min = parameter.value.frequency.min
        max = parameter.value.frequency.max

        val1 = max - (rand.random() * (max - min))
        val2 = max - (rand.random() * (max - min))
        val3 = max - (rand.random() * (max - min))

        parameter.value.frequency = [val1, val2, val3]

    return state
