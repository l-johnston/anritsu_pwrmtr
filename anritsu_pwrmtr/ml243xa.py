"""ML243xA series power meter"""
import sys
import asyncio
import itertools
import time
import pyvisa
from anritsu_pwrmtr.common import (
    InstrumentBase,
    get_idn,
    Subsystem,
    parse_number,
    State,
)


class ML243xA(InstrumentBase):
    """ML243xA class

    Attributes:
        visa (pyvisa.resources.Resource): pyvisa resource
    """

    def __init__(self, visa):
        super().__init__(visa)
        self._visa.write("*CLS")
        self._visa.read_termination = "\n"
        self._idn = get_idn(visa)
        self._channels = [Channel(self, x) for x in range(1, 3)]
        for x, ch in enumerate(self._channels, 1):
            setattr(self, f"ch{x}", ch)
        self._sensors = [Sensor(self, d) for d in ["A", "B"]]
        for sensor in self._sensors:
            setattr(self, f"sensor_{sensor._s}", sensor)

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
        """Get the status"""
        value = self._visa.query("STATUS")
        result = []
        i = 0
        for sk, sv in STATUS.items():
            if sk.endswith("range hold"):
                rh = int(value[i : i + 2])
                for rhk in sv:
                    if rh in rhk:
                        result.append(f"{sk}: {sv[rhk]}")
                        break
                i += 2
            elif sk.endswith("average number"):
                result.append(f"{sk}: {value[i:i+4]}")
                i += 4
            else:
                result.append(f"{sk}: {sv[value[i]]}")
                i += 1
        return result

    def self_test(self):
        """Perform a self-test"""
        return self._visa.query("*TST?")

    @property
    def display(self):
        """value : str
        Turn display ON or OFF
        """
        return self._visa.query("DISP?")

    @display.setter
    def display(self, value):
        self._visa.write(f"DISP {value}")

    @property
    def frequency_offset_display(self):
        """value : str
        Turn ON or OFF the display of frequency and offset of the sensors
        """
        return self._visa.query("FROFF?")

    @frequency_offset_display.setter
    def frequency_offset_display(self, value):
        self._visa.write(f"FROFF {value}")

    def factory_reset(self):
        """Reset to factory default configuration"""
        self._visa.write("FRST")
        # a time delay of ~1 s is required to prevent VISA timeout on subsequent write
        # the manual does provide any information on this
        time.sleep(1)

    @property
    def mode(self):
        """value : str
        Selects operating mode {digital readout, profile, power vs. time, source sweep}
        """
        value = self._visa.query("OPMD?").split("OPMD ")[-1]
        return MODE[value]

    @mode.setter
    def mode(self, value):
        MODE_rev = {v: k for k, v in MODE.items()}
        m = MODE_rev.get(value, value)
        self._visa.write(f"OPMD {m}")

    @property
    def text_display(self):
        """value : str
        Text to display. Setting to '' turns it off.
        """
        return self._visa.query("TEXT?")

    @text_display.setter
    def text_display(self, value):
        self._visa.write(f"TEXT {value}")
        if value == "":
            self._visa.write("TEXTS OFF")
        else:
            self._visa.write("TEXTS ON")


STATUS = {
    "Operating mode": {
        "0": "Digital readout",
        "1": "Profile mode channel 1",
        "2": "Profile mode channel 2",
        "3": "Power vs. Time channel 1",
        "4": "Power vs. Time channel 2",
    },
    "Channel 1 input configuration": {
        "0": "OFF",
        "1": "A",
        "2": "B",
        "3": "A-B",
        "4": "B-A",
        "5": "A/B",
        "6": "B/A",
        "7": "EXT Volts",
    },
    "Channel 2 input configuration": {
        "0": "OFF",
        "1": "A",
        "2": "B",
        "3": "A-B",
        "4": "B-A",
        "5": "A/B",
        "6": "B/A",
        "7": "EXT Volts",
    },
    "Channel 1 units": {"0": "dBm", "1": "W", "2": "V", "3": "dBmV", "4": "dBmV"},
    "Channel 2 units": {"0": "dBm", "1": "W", "2": "V", "3": "dBmV", "4": "dBmV"},
    "Channel 1 relative status": {"0": "OFF", "1": "ON"},
    "Channel 2 relative status": {"0": "OFF", "1": "ON"},
    "Channel 1 low limit state": {"0": "OFF", "1": "ON"},
    "Channel 1 high limit state": {"0": "OFF", "1": "ON"},
    "Channel 2 low limit state": {"0": "OFF", "1": "ON"},
    "Channel 2 high limit state": {"0": "OFF", "1": "ON"},
    "Sensor A measurement mode": {"0": "Default", "1": "MOD average", "2": "Custom"},
    "Sensor B measurement mode": {"0": "Default", "1": "MOD average", "2": "Custom"},
    "Sensor A range hold": {range(1, 6): "MANUAL", range(11, 16): "AUTO"},
    "Sensor B range hold": {range(1, 6): "MANUAL", range(11, 16): "AUTO"},
    "Sensor A averaging mode": {"0": "OFF", "1": "AUTO", "2": "MOVING", "3": "REPEAT"},
    "Sensor B averaging mode": {"0": "OFF", "1": "AUTO", "2": "MOVING", "3": "REPEAT"},
    "Sensor A average number": "",
    "Sensor B average number": "",
    "Sensor A low level average": {"0": "OFF", "1": "Low", "2": "Medium", "3": "High"},
    "Sensor B low level average": {"0": "OFF", "1": "Low", "2": "Medium", "3": "High"},
    "Sensor A zeroed status": {"0": "Not zeroed", "1": "Zeroed"},
    "Sensor B zeroed status": {"0": "Not zeroed", "1": "Zeroed"},
    "GPIB trigger mode": {"0": "TR0 hold ON", "1": "Free run"},
    "GPIB group trigger mode": {"0": "GT0", "1": "GT1", "2": "GT2"},
    "Calibrator state": {"0": "OFF", "1": "ON"},
    "GPIB DISP command status": {"0": "OFF", "1": "ON"},
    "GPIB FAST status": {"0": "OFF", "1": "ON"},
}

MODE = {
    "DIGIT": "digital readout",
    "PROFILE": "profile",
    "PWRTIM": "power vs. time",
    "SRCSWP": "source sweep",
}


class Channel(Subsystem, kind="Channel"):
    """Channel subsystem

    Attributes
    ----------
        instr : PowerMeter
        CHx : int
            Channel number {1, 2}
    """

    def __init__(self, instr, CHx):
        super().__init__(instr)
        self._ch = CHx

    @property
    def input_configuration(self):
        """value : str {OFF, A, B, V, A-B, B-A, A/B, B/A}"""
        value = self._visa.query(f"CHCFG? {self._ch}")
        result = value.split(",")[-1]
        return result

    @input_configuration.setter
    def input_configuration(self, value):
        self._visa.write(f"CHCFG {self._ch},{value}")

    @property
    def resolution(self):
        """value : int {1, 2, 3}"""
        value = self._visa.query(f"CHRES? {self._ch}")
        result = int(value.split(",")[-1])
        return result

    @resolution.setter
    def resolution(self, value):
        self._visa.write(f"CHRES {self._ch},{value}")

    @property
    def units(self):
        """value : str {W, dBm, dBmV}"""
        value = self._visa.query(f"CHUNIT? {self._ch}")
        result = value.split(",")[-1]
        return UNITS[result]

    @units.setter
    def units(self, value):
        UNITS_rev = {v: k for k, v in UNITS.items()}
        self._visa.write(f"CHUNIT {self._ch},{UNITS_rev[value]}")

    @property
    def minmax_values(self):
        """Return min and max values when tracking is enabled"""
        mn, mx = self._visa.query(f"GMNMX {self._ch}")
        return (float(mn), float(mx))

    def reset_minmax(self):
        """Reset min/max values"""
        self._visa.write(f"MMRST {self._ch}")

    @property
    def track_minmax(self):
        """value : str {ON, OFF}"""
        value = self._visa.query(f"MNMXS? {self._ch}")
        result = value.split(",")[-1]
        return result

    def read(self, samples=1, timeout=10, settle=False):
        """Return measured value(s)

        Parameters
        ----------
        samples : int
            Number of samples to return (1 to 1000)
        timeout : int
            Time out number of seconds
        settle : bool
            If settle and averaging ON, clear buffer and start acquisition, return
            one sample. So called 'trigger with settling delay'.
        """
        original_timeout = self._visa.timeout
        self._visa.timeout = 1000 * timeout
        if not settle:
            self._visa.write(f"ON {self._ch},{samples}")
        else:
            self._visa.write(f"TR2 {self._ch}")
        values = self._visa.read_ascii_values()
        self._visa.timeout = original_timeout
        if len(values) == 1:
            return values[0]
        return values


UNITS = {"W": "W", "DBM": "dBm", "DBUV": "dBmV", "DBMV": "dBmV"}


class Sensor(Subsystem, kind="Sensor"):
    """Sensor subsystem

    Attributes
    ----------
        instr : ML243xA
        designation : str
            Sensor {A, B}
    """

    def __init__(self, instr, designation):
        super().__init__(instr)
        self._s = designation
        self._state = State()

    @property
    def averaging(self):
        """Averaging mode, number and post-averaging filter"""
        value = self._visa.query(f"AVG? {self._s}")
        mode, n = value.split(",")[-2:]
        value = self._visa.query(f"AVGLL? {self._s}")
        post_filter = value.split(",")[-1]
        return f"Mode: {mode}, Number: {n}, Post-filter: {post_filter}"

    def set_averaging(self, mode="automatic", number=1, post_filter="low"):
        """Set the sensor averaging mode and number

        Parameters
        ----------
        mode : str
            Averaging mode {off, moving, repeat, automatic}
        number : int
            Number of averages (1-512) for 'moving' and 'repeat' modes
        post_filter : str
            Low-pass filter settling window {off, low, medium, high}
            Applied after averaging process
        """
        valid_values = []
        for item in AVERAGING.items():
            valid_values.extend(map(str.lower, item))
        if mode not in valid_values:
            raise ValueError(f"invalid mode '{mode}'")
        if not 0 < number < 513:
            raise ValueError(f"invalid number '{number}'")
        if post_filter.lower() not in ["off", "low", "medium", "high"]:
            raise ValueError(f"invalid post_filter '{post_filter}'")
        AVERAGING_rev = {v: k for k, v in AVERAGING.items()}
        mode = AVERAGING_rev.get(mode, mode).upper()
        self._visa.write(f"AVG {self._s},{mode},{number}")
        self._visa.write(f"AVGLL {self._s},{post_filter}")

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

    async def _cal(self):
        try:
            self._visa.write(f"*CLS;*ESE 17;*SRE 32;CAL {self._s};*OPC")
            # poll the RQS bit for service request
            while not self._visa.stb & 64:
                await asyncio.sleep(1)
            esr = int(self._visa.query("*ESR?"))
            # workaround. clear stb when cal fails
            self._visa.stb  # pylint: disable=pointless-statement
            exe_error = bool(esr & 16)
            op_complete = bool(esr & 1)
            return 0 if op_complete and not exe_error else 1
        except asyncio.CancelledError:
            pass
        except pyvisa.VisaIOError as exc:
            if exc.abbreviation == "VI_ERROR_TMO":
                raise TimeoutError(
                    "Acquisition timed out due to loss of communication"
                ) from None
            raise
        finally:
            self._state.running = False

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
                "Acquisition didn't complete before specified timeout value"
            ) from None
        else:
            return ret_value

    def cal(self):
        """Calibrate sensor to 0 dBm reference"""
        error = asyncio.run(self._start_task(self._cal(), 30))[1]
        if error:
            print(f"Sensor {self._s} calibrate to 0 dBm reference failed")

    async def _zero(self):
        try:
            self._visa.write(f"*CLS;*ESE 17;*SRE 32;ZERO {self._s};*OPC")
            # poll the RQS bit for service request
            while not self._visa.stb & 64:
                await asyncio.sleep(1)
            esr = int(self._visa.query("*ESR?"))
            # workaround. clear stb when zero fails
            self._visa.stb  # pylint: disable=pointless-statement
            exe_error = bool(esr & 16)
            op_complete = bool(esr & 1)
            return 0 if op_complete and not exe_error else 1
        except asyncio.CancelledError:
            pass
        except pyvisa.VisaIOError as exc:
            if exc.abbreviation == "VI_ERROR_TMO":
                raise TimeoutError(
                    "Acquisition timed out due to loss of communication"
                ) from None
            raise
        finally:
            self._state.running = False

    def zero(self):
        """Zero sensor"""
        error = asyncio.run(self._start_task(self._zero(), 30))[1]
        if error:
            print(f"Sensor {self._s} zeroing failed")

    @property
    def frequency(self):
        """value : float or str
        Cal factor frequency 9 kHz to 122 GHz
        """
        query_response = self._visa.query(f"CFFRQ? {self._s}")
        value = float(query_response.split(",")[-1])
        return value

    @frequency.setter
    def frequency(self, value):
        if isinstance(value, str):
            value = parse_number(value)
        if not 9e3 < value < 122e9:
            raise ValueError(f"invalid frequency '{value}'")
        self._visa.write(f"CFFRQ {self._s},{value}")

    @property
    def model(self):
        """Return model and serial number of sensor"""
        return self._visa.query(f"SENTYP {self._s}")


AVERAGING = {"OFF": "off", "MOV": "moving", "RPT": "repeat", "AUTO": "automatic"}
