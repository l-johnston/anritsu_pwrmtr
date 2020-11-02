"""MA243x0A series USB power sensor"""
import functools
from datetime import datetime
import sys
import asyncio
import itertools
import pyvisa
from anritsu_pwrmtr.common import (
    InstrumentBase,
    get_idn,
    Subsystem,
    State,
)

ERRORSTATUS = [
    "Temperature change of more than 10 °C after zeroing",
    "Operating temperature over range < 0 °C or > 60 °C",
    "High Power Detector zeroing error",
    "Mid Power Detector zeroing error",
    "Low Power Detector zeroing error",
]

MODE = [
    "Continuous Average",
    "Time Slot",
    "Scope",
    "Idle",
    "List",
]

AVGTYP = {"0": "Moving", "1": "Repeat"}

AVGMODE = {"0": "Off", "1": "On", "2": "Once"}
AVGRES = {"0": "1.0", "1": "0.1", "2": "0.01", "3": "0.001"}


def write(func):
    """Write <value> and return result message such as 'OK', 'BAD CMD', 'ERR'"""

    @functools.wraps(func)
    def inner(*args, **kwargs):
        _self = args[0]
        func(*args, **kwargs)
        return _self._visa.read()

    return inner


class MA243x0A(InstrumentBase):
    """MA243x0A class

    Attributes:
        visa (pyvisa.resources.Resource): pyvisa resource
    """

    def __init__(self, visa):
        super().__init__(visa)
        self._idn = get_idn(visa)
        self._state = State()
        self.trigger = Trigger(self)

    @property
    def model(self):
        """(str): the model number"""
        return self._idn.model

    @property
    def serial_number(self):
        """(str): the serial number"""
        return self._idn.serial_number

    @property
    def firmware_version(self):
        """(str): the firmware version"""
        return self._idn.firmware_version

    def __repr__(self):
        return f"<Anritsu {self.model} at {self._visa.resource_name}>"

    @property
    def status(self):
        """Get the status (errors)"""
        result = int(self._visa.query("STATUS?"))
        errors = [err for i, err in enumerate(ERRORSTATUS) if result & 2 ** i]
        return errors if errors else "no errors"

    @property
    def mode(self):
        """value : str {Continuous Average, Time Slot, Scope, Idle, List}"""
        i = int(self._visa.query("CHMOD?"))
        return MODE[i]

    @mode.setter
    @write
    def mode(self, value):
        try:
            i = MODE.index(value.title())
        except ValueError:
            raise ValueError(f"'{value}' not in {MODE}") from None
        self._visa.write(f"CHMOD {i}")

    @property
    def aperture_time(self):
        """value : float aperture time in milliseconds 0.01 ms to 1000 ms"""
        return float(self._visa.query("CHAPERT?"))

    @aperture_time.setter
    @write
    def aperture_time(self, value):
        if 0.01 <= value <= 1000:
            self._visa.write(f"CHAPERT {value}")
        else:
            raise ValueError(f"'{value}' not in 0.01 ms to 1000 ms")

    @property
    def frequency(self):
        """frequency : float frequency in gigahertz 0.000001 GHz to 50 GHz"""
        return float(self._visa.query("FREQ?"))

    @frequency.setter
    @write
    def frequency(self, value):
        if 0.000001 <= value <= 50:
            self._visa.write(f"FREQ {value}")
        else:
            raise ValueError(f"'{value}' not in 0.000001 GHz to 50 GHz")

    @property
    def temperature(self):
        """float current temperature of the sensor in celcius"""
        return float(self._visa.query("TMP?"))

    @property
    def cal_date(self):
        """datetime date of last calibration"""
        return datetime.strptime(self._visa.query("CALDATE"), "%m/%d/%Y %H:%M:%S")

    @write
    def reset(self):
        """Reset the sensor to factory default configuration"""
        self._visa.write("RST")

    async def _show_spinner(self):
        """Show an in-progress spinner during acquisition"""
        glyph = itertools.cycle(["-", "\\", "|", "/"])
        try:
            while self._state.running:
                sys.stdout.write(next(glyph))
                sys.stdout.flush()
                sys.stdout.write("\b")
                await asyncio.sleep(0.5)
            return 0
        except asyncio.CancelledError:
            pass
        finally:
            sys.stdout.write("\b \b")

    async def _zero(self):
        # zeroing takes ~25 s
        originaltimeout = self._visa.timeout
        self._visa.timeout = 100  # ms
        self._visa.write("ZERO")
        try:
            while True:
                await asyncio.sleep(10)
                try:
                    result = self._visa.read()
                except pyvisa.VisaIOError:
                    pass
                else:
                    break
            return 0 if result == "OK" else 1
        except asyncio.CancelledError:
            pass
        finally:
            self._state.running = False
            self._visa.timeout = originaltimeout

    async def _start_task(self, coroutine, timeout):
        """timeout : int timeout in seconds
        coroutine : awaitable
        """
        self._state.running = True
        task = asyncio.gather(self._show_spinner(), coroutine)
        try:
            ret_value = await asyncio.wait_for(task, timeout)
        except asyncio.TimeoutError:
            task.exception()  # retrieve the _GatheringFuture exception
            raise TimeoutError(
                "Operation didn't complete before specified timeout value"
            ) from None
        else:
            return ret_value

    def zero(self):
        """Zero the power sensor which takes 25 s"""
        error = asyncio.run(self._start_task(self._zero(), 30))[1]
        if error:
            raise RuntimeError(", ".join(self.status))

    @property
    def averaging_type(self):
        """value : str {Moving, Repeat}"""
        return AVGTYP[self._visa.query("AVGTYP?")]

    @averaging_type.setter
    @write
    def averaging_type(self, value):
        avgtyp = {v: k for k, v in AVGTYP.items()}
        self._visa.write(f"AVGTYP {avgtyp[value]}")

    @property
    def averaging_count(self):
        """value : int number of samples to average up to 65536"""
        return int(self._visa.query("AVGCNT?"))

    @averaging_count.setter
    @write
    def averaging_count(self, value):
        self._visa.write(f"AVGCNT {value}")

    @property
    def averaging_mode(self):
        """value : str auto-averaging mode {Off, On, Once}"""
        return AVGMODE[self._visa.query("AUTOAVG?")]

    @averaging_mode.setter
    @write
    def averaging_mode(self, value):
        avgmode = {v: k for k, v in AVGMODE.items()}
        self._visa.write(f"AUTOAVG {avgmode[value]}")

    @property
    def averging_resolution(self):
        """value : str resolution {1.0, 0.1, 0.01, 0.001} dB"""
        return AVGRES[self._visa.query("AUTOAVGRES?")]

    @averging_resolution.setter
    @write
    def averging_resolution(self, value):
        avgres = {v: k for k, v in AVGRES.items()}
        self._visa.write(f"AUTOAVGRES {avgres[value]}")

    @property
    def averaging_source(self):
        """value : int"""
        return int(self._visa.query("AUTOAVGSRC?"))

    @write
    def reset_averaging(self):
        """Clear the averaging buffer and restart"""
        self._visa.write("AVGRST")

    def read(self):
        """Read power in dBm"""
        cmd = "PWR?"
        result = self._visa.query(f"{cmd}")
        if result.startswith("e"):
            raise RuntimeError(", ".join(self.status))
        return float(result)

    def __dir__(self):
        attrs = super().__dir__()
        if self.mode != "Continuous Average":
            attrs.remove("aperture_time")
        return attrs


TRGSRC = {"0": "Continuous", "1": "Internal", "2": "External"}
TRGEDG = {"0": "Positive", "1": "Negative"}
TRGARM = {"0": "Auto", "1": "Single", "2": "Multi", "3": "Standby"}


class Trigger(Subsystem, kind="Trigger"):
    """Trigger subsystem

    Attributes
    ----------
        instr : MA243x0A
    """

    @property
    def source(self):
        """value : str {Continuous, Internal, External}"""
        return TRGSRC[self._visa.query("TRGSRC?")]

    @source.setter
    @write
    def source(self, value):
        trgsrc = {v: k for k, v in TRGSRC.items()}
        self._visa.write(f"TRGSRC {trgsrc[value]}")

    @property
    def level(self):
        """value : float -35 dBm to +20 dBm in 0.01 dB steps"""
        return float(self._visa.query("TRGLVL?"))

    @level.setter
    @write
    def level(self, value):
        self._visa.write(f"TRGLVL {value}")

    @property
    def edge(self):
        """value : str {Positive, Negative}"""
        return TRGEDG[self._visa.query("TRGEDG?")]

    @edge.setter
    @write
    def edge(self, value):
        trgedg = {v: k for k, v in TRGEDG.items()}
        self._visa.write(f"TRGEDG {trgedg[value]}")

    @property
    def delay(self):
        """value : float

        start of acquisition in milliseconds relative to trigger event
        -5 ms to +10000 ms in 0.01 ms steps
        """
        return float(self._visa.query("TRGDLY?"))

    @delay.setter
    @write
    def delay(self, value):
        self._visa.write(f"TRGDLY {value}")

    @property
    def holdoff(self):
        """value : float

        trigger supression in milliseconds after first detected event
        0 ms to 10000 ms in 0.01 ms steps
        """
        return float(self._visa.query("TRGHOLDDLY?"))

    @holdoff.setter
    @write
    def holdoff(self, value):
        self._visa.write(f"TRGHOLDDLY {value}")

    @property
    def hysteresis(self):
        """value : float hysteresis 0 dB to 10 dB in 0.1 dB steps"""
        return float(self._visa.query("TRGHYST?"))

    @hysteresis.setter
    @write
    def hysteresis(self, value):
        self._visa.write(f"TRGHYST {value}")

    def arm(self, mode="Auto"):
        """Arm the trigger

        Parameters
        ----------
        mode : str {"Auto", "Single", "Multi", "Standby"}
        """
        trgarm = {v: k for k, v in TRGARM.items()}
        self._visa.write(f"TRGARMTYP {trgarm[mode]}")
