"""LMR Master S412E"""
import sys
import itertools
import asyncio
from dateutil.parser import parse as dateutil_parse
import pyvisa
from anritsu_pwrmtr.common import (
    InstrumentBase,
    get_idn,
    Subsystem,
    parse_number,
    State,
)


class S412E(InstrumentBase):
    """S412E class

    Parameters
    ----------
    visa : pyvisa.resource.Resource
    """

    def __init__(self, visa):
        super().__init__(visa)
        self._visa.read_termination = "\n"
        self._idn = get_idn(visa)
        self._state = State()

    @property
    def model(self):
        """model : str"""
        # model string includes installed options delimited with '/'
        return self._idn.model.split("/")[0]

    @property
    def installed_options(self):
        """installed_options : list of str"""
        return self._idn.model.split("/")[1:]

    @property
    def serial_number(self):
        """serial_number : str"""
        return self._idn.serial_number

    @property
    def firmware_version(self):
        """firmware_version : str"""
        return self._idn.firmware_version

    def __repr__(self):
        m_str = self._idn.model.split("/")[0]
        return f"<Anritsu {m_str} at {self._visa.resource_name}>"

    async def _show_spinner(self):
        # show an in-progress spinner during command execution
        glyph = itertools.cycle(["-", "\\", "|", "/"])
        while self._state.running:
            sys.stdout.write(next(glyph))
            sys.stdout.flush()
            sys.stdout.write("\b")
            await asyncio.sleep(0.5)
        sys.stdout.write("\b \b")
        return 0

    async def _reset(self):
        # takes 30 s
        self._visa.write(":SYSTEM:PRESET")
        await asyncio.sleep(30)
        self._state.running = False
        return 0

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

    def reset(self):
        """Restore all application parameters to their factory preset values

        This command takes 30 s to complete.
        """
        asyncio.run(self._start_task(self._reset(), 40))

    @property
    def gps_information(self):
        """Current GPS information

        Returns
        -------
        gps_info : four-tuple (str, datetime.datetime, float, float)
            fix_status, datetime, latitude (rad), longitude (rad)
        """
        result = self._visa.query(":FETCH:GPS?").split(",")
        result = [value.strip() for value in result]
        fix_status = result[0]
        datetime = dateutil_parse(result[1])
        latitude = parse_number(result[2])
        longitude = parse_number(result[3])
        return (fix_status, datetime, latitude, longitude)
