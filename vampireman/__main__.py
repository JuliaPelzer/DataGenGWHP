# When running `python3 -m vampireman [...]` this file will be executed by python.
# It then runs the `invoke_vampireman()` function in ./cli.py
import logging
import warnings

# This supresses unwanted output as the library tries to write to its installation directory. Only required once.
with warnings.catch_warnings(action="ignore"):
    import numpydantic as numpydantic

from . import cli

# This needs to be set here, as the default logger is set to WARNING and we'd miss logging any info logs until the
# level is set correctly by the `invoke_vampireman()` function.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s: %(filename)s:%(lineno)s in %(funcName)s() > %(message)s"
)

if __name__ == "__main__":
    cli.invoke_vampireman()
