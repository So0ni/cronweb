from __future__ import annotations
import abc
import typing
import enum
import logging

if typing.TYPE_CHECKING:
    import cronweb


class JobStateEnum(enum.Enum):
    RUNNING = 1
    DONE = 2
    ERROR = 3
    KILLED = 4
    UNKNOWN = 5


class JobState(typing.NamedTuple):
    uuid: str
    state: JobStateEnum


class WorkerBase(abc.ABC):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__()
        self._core: typing.Optional[cronweb.CronWeb] = controller
        self._py_logger: logging.Logger = logging.getLogger(f'cronweb.{self.__class__.__name__}')

    def set_controller(self, controller: cronweb.CronWeb):
        self._core = controller

    @abc.abstractmethod
    async def shoot(self, command: str, param: str, uuid: str, timeout: float):
        pass

    @abc.abstractmethod
    def get_running_jobs(self) -> typing.Set[str]:
        pass

    @abc.abstractmethod
    def kill_all_running_jobs(self) -> typing.Set[str]:
        pass
