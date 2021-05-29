from __future__ import annotations
import abc
import typing
import pathlib
import logging

if typing.TYPE_CHECKING:
    import cronweb
    import trigger
    import worker


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
    async def get_job(self, uuid: str) -> trigger.JobInfo:
        """用uuid获取一个指定的job"""
        pass

    @abc.abstractmethod
    async def get_all_jobs(self) -> typing.Dict[str, trigger.JobInfo]:
        """获取数据库中所有job"""
        pass

    @abc.abstractmethod
    async def save_job(self, job_info: trigger.JobInfo):
        """添加一个新job到数据库"""
        pass

    @abc.abstractmethod
    async def job_log_shoot(self, uuid: str, log_path: typing.Union[str, pathlib.Path]):
        """新建一条job log的运行记录
        uuid 日志路径 状态(运行中)
        """
        pass

    @abc.abstractmethod
    async def job_log_done(self, uuid: str, job_state: worker.JobState):
        """修改job log的运行记录 状态为实际的状态"""
        pass

    @abc.abstractmethod
    async def job_log_get_by_id(self, uuid: str) -> typing.Optional[worker.JobState]:
        """通过uuid获取job log的状态"""
        pass

    @abc.abstractmethod
    async def job_log_get_by_state(self, state: worker.JobStateEnum) -> typing.Set[str]:
        """获取所有状态为指定状态的job log"""
        pass

    @abc.abstractmethod
    async def stop(self):
        pass
