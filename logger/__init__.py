from __future__ import annotations
import abc
import asyncio
import typing

if typing.TYPE_CHECKING:
    import cronweb


class LogStop(Exception):
    """stop logging"""


class LoggerBase(abc.ABC):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__()
        self._core: typing.Optional[cronweb.CronWeb] = controller

    def set_controller(self, controller: cronweb.CronWeb):
        self._core = controller

    @abc.abstractmethod
    def get_log_queue(self, uuid: str) -> asyncio.queues.Queue:
        pass
