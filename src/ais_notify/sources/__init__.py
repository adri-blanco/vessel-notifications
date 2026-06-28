"""Swappable AIS input sources."""

from ais_notify.sources.base import AISSource
from ais_notify.sources.udp_source import UDPSource
from ais_notify.sources.tcp_source import TCPSource
from ais_notify.sources.serial_source import SerialSource
from ais_notify.sources.file_source import FileSource

__all__ = ["AISSource", "UDPSource", "TCPSource", "SerialSource", "FileSource"]
