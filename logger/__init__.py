from __future__ import annotations
import abc
import asyncio
import datetime
import typing
import logging
import pathlib

if typing.TYPE_CHECKING:
    import cronweb


class LogStop(Exception):
    """stop logging"""


class LoggerBase(abc.ABC):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__()
        self._core: typing.Optional[cronweb.CronWeb] = controller
        self._py_logger: logging.Logger = logging.getLogger(f'cronweb.{self.__class__.__name__}')

    def set_controller(self, controller: cronweb.CronWeb):
        self._core = controller

    @abc.abstractmethod
    def get_log_queue(self, uuid: str, shot_id: str) -> typing.Tuple[asyncio.queues.Queue, pathlib.Path]:
        pass
