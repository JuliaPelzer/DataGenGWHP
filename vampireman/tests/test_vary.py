import numpy as np

from vampireman import preparation_stage, variation_stage
from vampireman.data_structures import (
    Distribution,
    HeatPump,
    Parameter,
    State,
    ValueMinMax,
    ValuePerlin,
    ValueTimeSeries,
    Vary,
)
from vampireman.utils import create_dataset_and_datapoint_dirs


def test_vary_copy():
    state = State()
    state.general.interactive = False

    create_dataset_and_datapoint_dirs(state)

    state.heatpump_parameters["hp1"] = Parameter(
        name="hp1",
        vary=Vary.FIXED,
        value=HeatPump(location=[16, 32, 1], injection_temp=13.6, injection_rate=0.00024),
    )

    temp_param = state.hydrogeological_parameters.get("temperature")
    hp_param = state.heatpump_parameters.get("hp1")

    assert len(state.datapoints) == 0
    state = preparation_stage(state)
    state = variation_stage(state)
    assert len(state.datapoints) == 1

    temp_data = state.datapoints[0].data.get("temperature")
    hp_data = state.datapoints[0].data.get("hp1")

    assert temp_param != temp_data
    assert temp_param.value == temp_data.value

    # Parameter value shouldn't change
    temp_data.value *= 6
    assert temp_param.value != temp_data.value

    assert hp_data.value.location == hp_param.value.location

    hp_data.value.location[0] = 123
    assert hp_data.value.location != hp_param.value.location


def test_vary_space():
    state = State()
    state.general.interactive = False
    state.general.number_datapoints = 2

    create_dataset_and_datapoint_dirs(state)

    state.hydrogeological_parameters["param_scalar"] = Parameter(
        name="param_scalar",
        vary=Vary.FIXED,
        value=1,
    )
    state.hydrogeological_parameters["param_perlin"] = Parameter(
        name="param_perlin",
        vary=Vary.SPACE,
        distribution=Distribution.LOG,
        value=ValuePerlin(frequency=[18, 18, 18], max=2, min=1),
    )

    param_scalar = state.hydrogeological_parameters.get("param_scalar")

    assert len(state.datapoints) == 0
    state = preparation_stage(state)
    state = variation_stage(state)
    assert len(state.datapoints) == 2

    data_scalar_0 = state.datapoints[0].data.get("param_scalar")
    data_scalar_1 = state.datapoints[1].data.get("param_scalar")

    data_perlin_0 = state.datapoints[0].data.get("param_perlin")
    data_perlin_1 = state.datapoints[1].data.get("param_perlin")

    # Should be equal across dataset
    assert data_scalar_0.value == data_scalar_1.value
    assert param_scalar.value == data_scalar_0.value

    # TODO: Write a better test
    assert not np.array_equal(data_perlin_0.value, data_perlin_1.value)


def test_vary_heatpump():
    state = State()
    state.general.interactive = False
    state.general.number_datapoints = 2

    create_dataset_and_datapoint_dirs(state)

    state.heatpump_parameters["hp1"] = Parameter(
        name="hp1",
        vary=Vary.SPACE,
        value=HeatPump(location=[16, 32, 1], injection_temp=13.6, injection_rate=0.00024),
    )

    hp_param = state.heatpump_parameters.get("hp1")

    assert len(state.datapoints) == 0
    state = preparation_stage(state)
    state = variation_stage(state)
    assert len(state.datapoints) == 2

    hp_data_0 = state.datapoints[0].data.get("hp1")
    hp_data_1 = state.datapoints[1].data.get("hp1")

    # XXX: These tests could be improved
    assert hp_data_0.value.location != hp_param.value.location
    assert hp_data_0.value.location != hp_data_1.value.location


def test_vary_const():
    # TODO: Write CONST&&ValueMinMaxArray test
    state = State()
    state.general.interactive = False
    state.general.shuffle_datapoints = False
    state.general.number_datapoints = 3

    create_dataset_and_datapoint_dirs(state)

    state.hydrogeological_parameters["parameter"] = Parameter(
        name="parameter",
        vary=Vary.CONST,
        value=ValueMinMax(min=1, max=5),
    )
    state.hydrogeological_parameters["parameter2"] = Parameter(
        name="parameter2",
        vary=Vary.CONST,
        value=ValueMinMax(min=-0.12, max=0.32),
    )

    param = state.hydrogeological_parameters.get("parameter")

    assert len(state.datapoints) == 0
    state = preparation_stage(state)
    state = variation_stage(state)
    assert len(state.datapoints) == 3

    data_0 = state.datapoints[0].data.get("parameter")
    data_1 = state.datapoints[1].data.get("parameter")
    data_2 = state.datapoints[2].data.get("parameter")

    assert data_0.value == param.value.min
    assert data_1.value == 3
    assert data_2.value == param.value.max

    data_0 = state.datapoints[0].data.get("parameter2")
    data_1 = state.datapoints[1].data.get("parameter2")
    data_2 = state.datapoints[2].data.get("parameter2")

    assert data_0.value == -0.12
    assert data_1.value == 0.1
    assert data_2.value == 0.32


def test_shuffle():
    state = State()
    state.general.interactive = False
    state.general.shuffle_datapoints = False
    state.general.number_datapoints = 30

    create_dataset_and_datapoint_dirs(state)

    state.hydrogeological_parameters["parameter"] = Parameter(
        name="parameter",
        vary=Vary.CONST,
        value=ValueMinMax(min=1, max=30),
    )

    state = preparation_stage(state)
    state = variation_stage(state)

    for i in range(28):
        this_value = state.datapoints[i].data.get("parameter").value
        next_value = state.datapoints[i + 1].data.get("parameter").value
        assert this_value < next_value
        assert this_value == i + 1

    state = State()
    state.general.interactive = False
    state.general.shuffle_datapoints = True
    state.general.number_datapoints = 30

    create_dataset_and_datapoint_dirs(state)

    state.hydrogeological_parameters["parameter"] = Parameter(
        name="parameter",
        vary=Vary.CONST,
        value=ValueMinMax(min=1, max=30),
    )

    state = preparation_stage(state)
    state = variation_stage(state)

    for i in range(28):
        this_value = state.datapoints[i].data.get("parameter").value
        # Actually this could be the case...
        assert this_value != i + 1


def test_time_based_conversion():
    state = State()

    state.heatpump_parameters = {
        "hp1": Parameter(
            name="hp1",
            value=HeatPump(location=[1, 1, 1], injection_temp=10, injection_rate=0.01),
        )
    }

    assert state.heatpump_parameters.get("hp1").value.injection_temp == 10
    state = preparation_stage(state)
    assert state.heatpump_parameters.get("hp1").value.injection_temp.values.get(0) == 10


def test_time_based_provided_values():
    state = State()

    state.heatpump_parameters = {
        "hp1": Parameter(
            name="hp1",
            value=HeatPump(
                location=[1, 1, 1],
                injection_temp=ValueTimeSeries(
                    values={
                        0: 0,
                        1: 1,
                        2: 2,
                        3: 3,
                        4: 4,
                    }
                ),
                injection_rate=0.01,
            ),
        )
    }

    state = preparation_stage(state)
    for i in range(2):
        assert state.heatpump_parameters.get("hp1").value.injection_temp.values.get(i) == i


def test_time_based_state():
    state = State(
        **{
            "general": {
                "interactive": False,
            },
            "heatpump_parameters": {
                "hp1": {
                    "name": "hp1",
                    "value": {
                        "location": [1, 1, 1],
                        "injection_temp": {
                            "time_unit": "day",
                            "values": {
                                1: 1,
                            },
                        },
                        "injection_rate": 0.001,
                    },
                }
            },
        }
    )

    state = preparation_stage(state)
    assert state.heatpump_parameters.get("hp1").value.injection_temp.values.get(1) == 1
