from __future__ import annotations
import abc
import typing
import pathlib
import logging
import datetime

if typing.TYPE_CHECKING:
    import cronweb
    import trigger
    import worker


class LogRecord(typing.NamedTuple):
    shot_id: str
    uuid: str
    state: str
    log_path: str
    date_start: str
    date_end: typing.Optional[str] = None


class StorageBase(abc.ABC):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__()
        self._core: typing.Optional[cronweb.CronWeb] = controller
        self._py_logger: logging.Logger = logging.getLogger(f'cronweb.{self.__class__.__name__}')

    def set_controller(self, controller: cronweb.CronWeb):
        self._core = controller

    @classmethod
    @abc.abstractmethod
    async def create(cls, *args, **kwargs):
        pass

    @abc.abstractmethod
    async def init_db(self):
        """初始化数据库表等操作"""
        pass

    @abc.abstractmethod
    async def get_job(self, uuid: str) -> typing.Optional[trigger.JobInfo]:
        """用uuid获取一个指定的job"""
        pass

    @abc.abstractmethod
    async def get_all_jobs(self) -> typing.Dict[str, trigger.JobInfo]:
        """获取数据库中所有job"""
        pass

    @abc.abstractmethod
    async def save_job(self, job_info: trigger.JobInfo) -> typing.Optional[trigger.JobInfo]:
        """添加一个新job到数据库"""
        pass

    @abc.abstractmethod
    async def remove_job(self, uuid: str) -> typing.Optional[str]:
        """从数据库删除一个job"""
        pass

    @abc.abstractmethod
    async def job_log_shoot(self, log_path: typing.Union[str, pathlib.Path],
                            shot_state: worker.JobState):
        """新建一条job log的运行记录
        uuid 日志路径 状态(运行中)
        返回log id
        """
        pass

    @abc.abstractmethod
    async def job_log_done(self, shot_state: worker.JobState):
        """修改job log的运行记录 状态为实际的状态"""
        pass

    @abc.abstractmethod
    async def job_logs_get_by_uuid(self, uuid: str) -> typing.List[LogRecord]:
        """通过uuid获取job log的状态"""
        pass

    @abc.abstractmethod
    async def job_logs_get_by_state(self, state: worker.JobStateEnum) -> typing.List[LogRecord]:
        """获取所有状态为指定状态的job log"""
        pass

    @abc.abstractmethod
    async def stop(self):
        pass
