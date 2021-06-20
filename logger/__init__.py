from __future__ import annotations
import abc
import asyncio
import typing
import logging
import pathlib

if typing.TYPE_CHECKING:
    import cronweb


class LogStop(Exception):
    """stop logging"""


class LoggerBase(abc.ABC):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None, **kwargs):
        super().__init__()
        self._core: typing.Optional[cronweb.CronWeb] = controller
        self._py_logger: logging.Logger = logging.getLogger(f'cronweb.{self.__class__.__name__}')
        self.controller_default()

    def set_controller(self, controller: cronweb.CronWeb):
        self._core = controller

    def controller_default(self):
        if self._core is not None:
            self._core.set_log_default(self)

    @abc.abstractmethod
    def get_log_queue(self, uuid: str, shot_id: str,
                      timeout_log: float) -> typing.Tuple[asyncio.queues.Queue, pathlib.Path]:
        pass

    @abc.abstractmethod
    async def read_log_by_path(self, log_path: typing.Union[str, pathlib.Path],
                               limit_line: int = 1000) -> typing.Optional[str]:
        pass

    @abc.abstractmethod
    def remove_log_file(self, log_path: typing.Union[str, pathlib.Path]) -> typing.Optional[pathlib.Path]:
        pass

    @abc.abstractmethod
    def get_all_log_file_path(self) -> typing.List[pathlib.Path]:
        """获取所有日志文件的Path对象列表."""
        pass
