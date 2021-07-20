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


class JobTypeEnum(enum.Enum):
    SCHEDULE = 1
    RETRY = 2
    MANUAL = 3


class JobState(typing.NamedTuple):
    uuid: str
    state: JobStateEnum
    shot_id: str
    date_start: str
    date_end: str = ''


class WorkerBase(abc.ABC):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None, **kwargs):
        super().__init__()
        self._core: typing.Optional[cronweb.CronWeb] = controller
        self._py_logger: logging.Logger = logging.getLogger(f'cronweb.{self.__class__.__name__}')
        self.controller_default()
        self._job_done_hooks: typing.List[
            typing.Callable[[str, str, JobStateEnum, JobTypeEnum], typing.Coroutine[None]]] = []

    def add_job_done_hook(self, func: typing.Callable[[str, str, JobStateEnum, JobTypeEnum], typing.Coroutine[None]]):
        if func not in self._job_done_hooks:
            self._job_done_hooks.append(func)

    def set_controller(self, controller: cronweb.CronWeb):
        self._core = controller

    def controller_default(self):
        if self._core is not None:
            self._core.set_worker_default(self)

    @abc.abstractmethod
    async def shoot(self, command: str, param: str, uuid: str, timeout: float, name: str, job_type: JobTypeEnum):
        pass

    @abc.abstractmethod
    def get_running_jobs(self) -> typing.Dict[str, typing.Tuple[str, str]]:
        pass

    @abc.abstractmethod
    async def kill_all_running_jobs(self) -> typing.Dict[str, str]:
        pass

    @abc.abstractmethod
    async def kill_by_shot_id(self, shot_id: str) -> typing.Optional[str]:
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    @abc.abstractmethod
    def __contains__(self, shot_id: str) -> bool:
        pass
