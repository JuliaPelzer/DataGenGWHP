import logging
from argparse import Namespace

from .config import Config, Workflow, load_config
from .prepare_simulation.pflotran.pflotran_in_renderer import render
from .vary_params import pflotran


def wait_for_confirmation(config: Config, next_stage: str = ""):
    if not config.general.interactive:
        return
    try:
        match input(f"Do you want to continue? {f"Next stage: {next_stage} " if next_stage else ""}Y/n "):
            case "n" | "N" | "no":
                logging.info("Exiting as instructed")
                exit(0)
    except KeyboardInterrupt:
        logging.info("Exiting as instructed")
        exit(0)


def run_vary_params(config: Config) -> Config:
    wait_for_confirmation(config, "Running stage parameter variation")

    match config.general.workflow:
        case Workflow.PFLOTRAN:
            return pflotran.vary_params(config)
        case _:
            logging.error("%s varying is not yet implemented", config.general.workflow)
            raise NotImplementedError()


def run_render(config: Config):
    wait_for_confirmation(config, "Running stage prepare_simulation")
    render(config)


def run(args: Namespace):
    config = load_config(args)
    print(config)
    logging.debug("Will run all stages")
    config = run_vary_params(config)
    run_render(config)
