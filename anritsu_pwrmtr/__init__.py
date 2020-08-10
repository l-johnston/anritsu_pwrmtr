"""anritsu_pwrmtr - an interface to the Anritsu power meters
"""
import pyvisa
from anritsu_pwrmtr.common import get_idn
from anritsu_pwrmtr.pwrmeter import PowerMeter
from anritsu_pwrmtr.version import __version__

__all__ = ["CommChannel"]


class CommChannel:
    """Connect to an Anritsu power meter using VISA

    Attributes:
        address (int): instrument's GPIB address, e.g. 13

    Returns:
        CommChannel or PowerMeter
    """

    def __init__(self, address):
        self._address = address
        self._rm = pyvisa.ResourceManager()
        self._visa = self._rm.open_resource(f"GPIB::{address}")
        self._visa.read_termination = "\n"

    def __enter__(self):
        self._visa.write("*CLS")
        idn = get_idn(self._visa)
        if idn.manufacturer != "ANRITSU" and not idn.model.startswith("ML"):
            raise ValueError(
                f"Device at {self._address} is a not an Anritsu power meter"
            )
        return PowerMeter(self._visa)

    def __exit__(self, exc_type, exc_value, exc_tb):
        self._visa.close()
        self._rm.close()

    def get_instrument(self):
        """Return the PowerMeter instrument object"""
        return self.__enter__()

    def close(self):
        """Close the CommChannel"""
        self.__exit__(None, None, None)


def __dir__():
    return ["CommChannel", "__version__"]
