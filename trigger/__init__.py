from __future__ import annotations
import abc
import typing
import logging
import croniter

if typing.TYPE_CHECKING:
    import cronweb


class JobInfo(typing.NamedTuple):
    uuid: str
    cron_exp: str
    command: str
    param: str
    name: str
    date_create: str
    date_update: str


class JobDuplicateError(Exception):
    """add duplicate job"""


class TriggerBase(abc.ABC):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__()
        self._core: typing.Optional[cronweb.CronWeb] = controller
        self._py_logger: logging.Logger = logging.getLogger(f'cronweb.{self.__class__.__name__}')

    def set_controller(self, controller: cronweb.CronWeb):
        self._core = controller

    @abc.abstractmethod
    def add_job(self, cron_exp: str, command: str, param: str,
                date_create: str, date_update: typing.Optional[str] = None,
                uuid: typing.Optional[str] = None, name: str = '') -> JobInfo:
        pass

    @abc.abstractmethod
    def update_job(self, uuid: str, cron_exp: str, command: str, param: str,
                   date_update: str,
                   name: str = '') -> JobInfo:
        pass

    @abc.abstractmethod
    def remove_job(self, uuid: str) -> JobInfo:
        pass

    @abc.abstractmethod
    def get_jobs(self) -> typing.Dict[str, JobInfo]:
        pass

    @abc.abstractmethod
    def stop_all(self) -> typing.Dict[str, JobInfo]:
        pass

    @staticmethod
    @abc.abstractmethod
    def cron_is_valid(cron_exp: str) -> bool:
        pass

    @abc.abstractmethod
    def __contains__(self, uuid: str) -> bool:
        pass
