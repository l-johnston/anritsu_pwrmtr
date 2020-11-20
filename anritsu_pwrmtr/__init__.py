"""anritsu_pwrmtr - an interface to the Anritsu power meters
"""
import pyvisa
from anritsu_pwrmtr.common import get_idn
from anritsu_pwrmtr.ml243xa import ML243xA
from anritsu_pwrmtr.ma243x0a import MA243x0A
from anritsu_pwrmtr.lmr_master.s412e import S412E
from anritsu_pwrmtr.version import __version__

__all__ = ["CommChannel"]

# Supported model to class lookup table
PWRMTR = {
    "ML2437A": ML243xA,
    "ML2438A": ML243xA,
    "MA24330A": MA243x0A,
    "S412E": S412E,
}


class CommChannel:
    """Connect to an Anritsu power meter using VISA

    Attributes
    ----------
        address : int or str
            instrument's GPIB address, e.g. 13, or USB address, e.g. 'USB0::0x...::RAW'

    Returns:
        CommChannel or PowerMeter
    """

    def __init__(self, address):
        self._address = address
        self._rm = pyvisa.ResourceManager()
        if isinstance(address, int):
            self._visa = self._rm.open_resource(f"GPIB::{address}")
        else:
            self._visa = self._rm.open_resource(address)
            self._visa.write_termination = "\n"
        self._visa.read_termination = "\n"

    def __enter__(self):
        idn = get_idn(self._visa)
        if idn.manufacturer.lower() != "anritsu":
            raise ValueError(
                f"Device at {self._address} is a not an Anritsu instrument"
            )
        # some models append installed options as '/' delimited
        m_str = idn.model.split("/")[0]
        return PWRMTR[m_str](self._visa)

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
