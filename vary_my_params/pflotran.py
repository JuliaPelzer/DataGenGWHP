from .config import Config
from .prepare_simulation import pflotran as pflotran_render
from .run_simulation import pflotran as pflotran_run
from .visualize import pflotran as pflotran_visualize


def render(config: Config):
    return pflotran_render.render(config)


def run_simulation(config: Config):
    return pflotran_run.run_simulation(config)


def plot_simulation(config: Config):
    return pflotran_visualize.plot_simulation(config)
