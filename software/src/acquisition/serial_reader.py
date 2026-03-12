"""
acquisition/serial_reader.py
Reads JSON messages from the embedded SPT device over a serial (USB/UART)
connection and forwards them to a DataProcessor instance.

The reader runs in a background daemon thread so the GUI/main thread
remains responsive.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, List, Optional

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from .data_processor import DataProcessor

logger = logging.getLogger(__name__)

# Default serial parameters matching the firmware
DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 1.0    # seconds
RECONNECT_DELAY = 2.0    # seconds between reconnect attempts


class SerialReader:
    """
    Manages a serial connection to the SPT device.

    Example::

        processor = DataProcessor(on_blow=lambda b: print(b))
        reader = SerialReader(processor)
        reader.start("/dev/ttyUSB0")
        ...
        reader.stop()
    """

    def __init__(
        self,
        processor: DataProcessor,
        baud: int = DEFAULT_BAUD,
        timeout: float = DEFAULT_TIMEOUT,
        on_connect: Optional[Callable[[str], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._processor = processor
        self._baud = baud
        self._timeout = timeout
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_error = on_error

        self._port_name: str = ""
        self._serial: Optional["serial.Serial"] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._connected = False

    # ── Public API ─────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def port_name(self) -> str:
        return self._port_name

    def start(self, port: str) -> None:
        """Open the serial port and start the background reader thread."""
        if not SERIAL_AVAILABLE:
            raise RuntimeError(
                "pyserial is not installed. Run: pip install pyserial"
            )
        self._port_name = port
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="SerialReader", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the reader thread to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._close_port()

    def send_command(self, cmd: str, params: Optional[dict] = None) -> bool:
        """
        Send a JSON command to the device.

        :param cmd:    Command name ("start", "stop", "reset", "zero", etc.)
        :param params: Optional extra fields to include in the JSON message.
        :return: True if the message was sent successfully.
        """
        if not self._connected or self._serial is None:
            logger.warning("Cannot send command – not connected")
            return False
        import json
        payload: dict = {"cmd": cmd}
        if params:
            payload.update(params)
        try:
            line = json.dumps(payload) + "\n"
            self._serial.write(line.encode("ascii"))
            return True
        except Exception as exc:
            logger.error("Failed to send command %r: %s", cmd, exc)
            return False

    @staticmethod
    def list_ports() -> List[str]:
        """Return a list of available serial port names."""
        if not SERIAL_AVAILABLE:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    # ── Background thread ──────────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._open_port()
                self._read_loop()
            except Exception as exc:
                logger.error("Serial error: %s", exc)
                if self._on_error:
                    self._on_error(str(exc))
            finally:
                self._close_port()
            if not self._stop_event.is_set():
                logger.info(
                    "Reconnecting to %s in %.1f s…",
                    self._port_name,
                    RECONNECT_DELAY,
                )
                time.sleep(RECONNECT_DELAY)

    def _open_port(self) -> None:
        self._serial = serial.Serial(
            port=self._port_name,
            baudrate=self._baud,
            timeout=self._timeout,
        )
        self._connected = True
        logger.info("Connected to %s at %d baud", self._port_name, self._baud)
        if self._on_connect:
            self._on_connect(self._port_name)

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._serial is None:
                break
            raw = self._serial.readline()
            if raw:
                try:
                    line = raw.decode("ascii", errors="replace")
                    self._processor.process_line(line)
                except Exception as exc:
                    logger.warning("Line processing error: %s", exc)

    def _close_port(self) -> None:
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        if self._connected:
            self._connected = False
            logger.info("Disconnected from %s", self._port_name)
            if self._on_disconnect:
                self._on_disconnect()
