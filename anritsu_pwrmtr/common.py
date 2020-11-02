"""Common definitions"""
from collections import namedtuple
import functools
import re
from dataclasses import dataclass

IDN = namedtuple("IDN", ["manufacturer", "model", "serial_number", "firmware_version"])

BOOLEAN = {"0": "OFF", "1": "ON"}

# regex pattern for mantissa of numeric value
P1 = r"[+-]?[0-9]+\.?[0-9]*"
# pattern for exponent in scientific notation
P2 = "[eE][+-][0-9]+"
# pattern for exponent in SI notation
SI_PREFIXES = "kMG"
UNITS = "Hz"
P3 = f" ?[{SI_PREFIXES}]"
NUMBER = f"^(?P<mantissa>{P1})(?P<exponent>{P2}|{P3})?( ?{UNITS})?$"


@dataclass
class State:
    """Signal for controlling asyncio tasks"""

    running: bool = False


def parse_number(n):
    """Parse number into float

    Parameters
    ----------
    n : str
        Number to parse e.g. 1e6, 1 MHz
    """
    m = re.match(NUMBER, n)
    if m is None:
        raise ValueError(f"invalid number '{n}'")
    mantissa, exponent, _ = m.groups()
    if exponent.strip() in SI_PREFIXES:
        exponent = f"E{3*(SI_PREFIXES.index(exponent.strip())+1)}"
    return float(mantissa + exponent)


def get_idn(visa):
    """Get IDN"""
    idn = visa.query("*IDN?").strip(":\n").split(",")
    return IDN(*idn)


class CommandError(Exception):
    """Raised when CME bit of SESR is set"""


def validate(func):
    """Read the Command Error bit (CME) of the Event-Status Register (ESR)"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # pylint: disable=protected-access
        cme = 32
        self = args[0]
        self._visa.write("*CLS")
        self._visa.write("SYSTEM:ERROR:CLEAR:ALL")
        original_ese = int(self._visa.query("*ESE?"))
        self._visa.write(f"*ESE {cme}")
        result = func(*args, **kwargs)
        if bool(int(self._visa.query("*ESR?")) & cme):
            err_id, err_msg = self._visa.query("SYSTEM:ERROR?").split(",")
            err_id = int(err_id)
            err_msg = err_msg.strip('"\r')
            raise CommandError(err_msg)
        self._visa.write(f"*ESE {original_ese}")
        return result

    return wrapper


class InstrumentBase:
    """Instrument base class

    Attributes:
        visa (pyvisa.resources.Resource): pyvisa resource
    """

    def __init__(self, visa):
        self._visa = visa

    def __setattr__(self, name, value):
        if hasattr(self, name) and isinstance(getattr(self, name), InstrumentBase):
            raise AttributeError(f"can't set '{name}'")
        if hasattr(self.__class__, name):
            prop = getattr(self.__class__, name)
            try:
                prop.fset(self, value)
            except TypeError:
                raise AttributeError(f"can't set '{name}'") from None
        else:
            self.__dict__[name] = value

    def __repr__(self):
        raise NotImplementedError

    def __dir__(self):
        inst_attr = list(filter(lambda k: not k.startswith("_"), self.__dict__.keys()))
        cls_attr = list(filter(lambda k: not k.startswith("_"), dir(self.__class__)))
        return inst_attr + cls_attr


class Subsystem(InstrumentBase):
    """Base class for a specific measurement function

    Attributes
    ----------
        instr : PowerMeter
    """

    _kind = "Instrument"

    def __init__(self, instr):
        super().__init__(instr._visa)
        self._instr = instr

    def __init_subclass__(cls, kind):
        cls._kind = kind

    def __get__(self, instance, owner=None):
        return self

    def __repr__(self):
        return f"<{self._instr.model} {self._kind}>"
