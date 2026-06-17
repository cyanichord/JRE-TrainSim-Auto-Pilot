import logging
from dataclasses import dataclass

import pymem

@dataclass
class GameState:
    speed_kmh:     float = 0.0
    max_speed_kmh: float = 110.0
    limit_kmh:     float = 110.0
    distance_m:    float = 9999.0
    gear_raw:      str   = ""
    power_notch:   int   = 0
    brake_notch:   int   = 0
    valid:         bool  = False
    is_pass_stop:  bool  = False

class MemoryReader:
    """Reads game variables directly from JREAST_TrainSimulator.exe memory."""

    # Confirmed static offsets (from exe base).
    # Verify these against your Cheat Engine scan if values are still wrong.
    OFFSET_SPEED     = 0x14CDB68   # float  – current speed km/h
    OFFSET_MAX_SPEED = 0x14F8E74   # int32  – train absolute max speed km/h
    OFFSET_LIMIT     = 0x14F8E78   # int32  – current posted speed limit km/h  ← ADD THIS
    OFFSET_DISTANCE  = 0x1511A58   # float  – distance to next station (m)
    OFFSET_POWER     = 0x10E2E30   # int32  – power notch
    OFFSET_BRAKE     = 0x10E2E38   # int32  – brake notch

    def __init__(self):
        self.pm        = None
        self.exe_base  = 0
        self.dll_base  = 0
        self._connect()

    def _connect(self) -> bool:
        """
        Attempt to attach to the game process.
        Returns True on success, False on failure.
        Only clears self.pm on a definitive failure so partial state isn't left behind.
        """
        try:
            pm       = pymem.Pymem("JREAST_TrainSimulator.exe")
            exe_base = pymem.process.module_from_name(
                pm.process_handle, "JREAST_TrainSimulator.exe"
            ).lpBaseOfDll
        except Exception as exc:
            logging.debug("MemoryReader._connect failed: %s", exc)
            self.pm       = None
            self.exe_base = 0
            return False

        # DLL is optional – don't bail if missing
        dll_base = 0
        try:
            dll_base = pymem.process.module_from_name(
                pm.process_handle, "TrainUnit_DLL.dll"
            ).lpBaseOfDll
        except Exception as exc:
            logging.debug("TrainUnit_DLL.dll not found (optional): %s", exc)

        self.pm       = pm
        self.exe_base = exe_base
        self.dll_base = dll_base
        logging.info("MemoryReader attached. exe_base=0x%X dll_base=0x%X",
                     exe_base, dll_base)
        return True

    def _read_int32(self, offset: int) -> int:
        """Read a signed 32-bit integer from exe_base + offset."""
        return self.pm.read_int(self.exe_base + offset)

    def _read_float(self, offset: int) -> float:
        """Read a 32-bit float from exe_base + offset."""
        return self.pm.read_float(self.exe_base + offset)
    
    def _read_double(self, offset: int) -> float:
        """Read a 64-bit double from exe_base + offset."""
        return self.pm.read_double(self.exe_base + offset)

    def read(self) -> GameState:
        state = GameState()

        if not self.pm:
            if not self._connect():
                return state   # still no connection – return invalid state

        try:
            state.speed_kmh    = self._read_double(self.OFFSET_SPEED)
            state.max_speed_kmh = float(self._read_int32(self.OFFSET_MAX_SPEED))

            # FIX Bug 4: read posted limit from its own address, not from max_speed
            raw_limit = self._read_int32(self.OFFSET_LIMIT)
            # Guard: if the limit address hasn't been mapped yet it may return 0
            state.limit_kmh = float(raw_limit) if raw_limit > 0 and raw_limit < state.max_speed_kmh else state.max_speed_kmh

            state.distance_m   = self._read_double(self.OFFSET_DISTANCE)
            state.power_notch  = self._read_int32(self.OFFSET_POWER)
            state.brake_notch  = self._read_int32(self.OFFSET_BRAKE)

            # Build gear display string
            if state.brake_notch == 9:
                state.gear_raw = "EMG"
            elif state.brake_notch > 0:
                state.gear_raw = f"B{state.brake_notch}"
            elif state.power_notch > 0:
                state.gear_raw = f"P{state.power_notch}"
            else:
                state.gear_raw = "N"

            state.valid = True

        except pymem.exception.MemoryReadError as exc:
            # FIX Bug 3: only drop the connection for genuine read errors,
            # not for every Python exception (e.g. a bad cast).
            logging.warning("Memory read error – will reconnect: %s", exc)
            self.pm = None
            state.valid = False

        except Exception as exc:
            # Non-memory errors (type errors, value errors, etc.) – log and
            # leave the process handle intact so we don't thrash reconnects.
            logging.warning("Unexpected error in MemoryReader.read: %s", exc)
            state.valid = False

        return state
