import datetime

import storage
import trigger
import worker
import web
import logger
import typing
import asyncio
import logging
import pathlib

import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


class CronWeb:
    def __init__(self,
                 worker_instance: typing.Optional[worker.WorkerBase] = None,
                 storage_instance: typing.Optional[storage.StorageBase] = None,
                 trigger_instance: typing.Optional[trigger.TriggerBase] = None,
                 web_instance: typing.Optional[web.WebBase] = None,
                 aiolog_instance: typing.Optional[logger.LoggerBase] = None
                 ):
        super().__init__()
        self._worker: typing.Optional[worker.WorkerBase] = worker_instance
        self._storage: typing.Optional[storage.StorageBase] = storage_instance
        self._trigger: typing.Optional[trigger.TriggerBase] = trigger_instance
        self._web: typing.Optional[web.WebBase] = web_instance
        self._aiolog: typing.Optional[logger.LoggerBase] = aiolog_instance
        self._py_logger: logging.Logger = logging.getLogger(f'cronweb.{self.__class__.__name__}')

    def set_storage(self, storage_instance: storage.StorageBase):
        self._storage = storage_instance
        return self

    def set_trigger_default(self, trigger_instance: trigger.TriggerBase):
        self._trigger = trigger_instance
        return self

    def set_worker_default(self, worker_instance: worker.WorkerBase):
        self._worker = worker_instance
        return self

    def set_web_default(self, web_instance: web.WebBase):
        self._web = web_instance
        return self

    def set_log_default(self, aiolog_instance: logger.LoggerBase):
        self._aiolog: typing.Optional[logger.LoggerBase] = aiolog_instance
        return self

    async def shoot(self, command: str, param: str, uuid: str, timeout: float = 1800) -> None:
        """使用worker执行job"""
        self._py_logger.info('分发任务到worker uuid:%s', uuid)
        return await self._worker.shoot(command, param, uuid, timeout)

    async def add_job(self, cron_exp: str, command: str, param: str,
                      uuid: typing.Optional[str] = None, name: str = '') -> typing.Optional[trigger.JobInfo]:
        """添加job 添加到trigger和storage 如果不指定uuid则自动创建uuid
        成功添加返回job info 失败(uuid已存在)返回None
        """
        self._py_logger.info('尝试添加任务')
        now = datetime.datetime.now()
        job = self._trigger.add_job(cron_exp, command, param, str(now), uuid=uuid, name=name)
        if job is not None:
            await self._storage.save_job(job)
        return job

    def cron_is_valid(self, cron_exp: str) -> bool:
        """判断cron表达式是否有效"""
        return self._trigger.cron_is_valid(cron_exp)

    async def update_job(self, uuid: str, cron_exp: str, command: str, param: str,
                         name: str = '') -> typing.Optional[trigger.JobInfo]:
        """更新指定uuid的job 这项操作并不会停止正在运行的job 但是会从trigger和storage中更新
        成功更新返回job info 失败(uuid不存在)返回None
        """
        self._py_logger.info('尝试更新任务')
        job = self._trigger.update_job(cron_exp, command, param, uuid, name)
        if job is not None:
            await self._storage.remove_job(uuid)
            await self._storage.save_job(job)
        return job

    async def remove_job(self, uuid: str) -> typing.Optional[trigger.JobInfo]:
        """删除指定uuid的job 这项操作并不会停止正在运行的job 但是会从trigger和storage中删除
        成功删除返回job info 失败(uuid不存在)返回None
        """
        self._py_logger.info('尝试删除任务')
        job = self._trigger.remove_job(uuid)
        if job is not None:
            await self._storage.remove_job(uuid)
            await self._storage.job_logs_set_deleted(uuid)
        return job

    async def get_jobs(self) -> typing.Dict[str, trigger.JobInfo]:
        """获取所有job的dict 获取前会执行job检查"""
        self._py_logger.info('尝试获取所有任务')
        await self.job_check()
        return self._trigger.get_jobs()

    def stop_all_trigger(self) -> typing.Dict[str, trigger.JobInfo]:
        """停止trigger中的所有任务 但是并不从中删除(暂时不考虑写入数据库 用于停止后避免启动新进程)"""
        return self._trigger.stop_all()

    def get_log_queue(self, uuid: str, shot_id: str) -> typing.Tuple[asyncio.queues.Queue, pathlib.Path]:
        """获取对应uuid的日志queue实例 运行开始时间和结束时间由queue实例写入"""
        return self._aiolog.get_log_queue(uuid, shot_id)

    def stop_running_by_shot_id(self, shot_id: str) -> typing.Optional[str]:
        """通过shot_id结束正在运行的进程 返回shot_id None则为shot_id未运行"""
        return self._worker.kill_by_shot_id(shot_id)

    async def job_logs_get_by_uuid(self, uuid: str) -> typing.List[storage.LogRecord]:
        """通过uuid在storage中取出运行记录"""
        return await self._storage.job_logs_get_by_uuid(uuid)

    async def job_log_get_by_shot_id(self, shot_id: str, limit_line: int = 1000) -> typing.Optional[str]:
        """通过shot_id获取日志文件内容"""
        record = await self._storage.job_log_get_record(shot_id)
        if not record:
            return None
        log_str = await self._aiolog.read_log_by_path(pathlib.Path(record.log_path), limit_line)
        return log_str

    def stop_all_running_jobs(self) -> typing.Dict[str, str]:
        """停止worker所有运行中的job 并返回成功结束的job {shot_id: uuid}"""
        return self._worker.kill_all_running_jobs()

    def get_all_running_jobs(self) -> typing.Dict[str, str]:
        """从worker中获取正在运行中的job {shot_id: uuid}"""
        return self._worker.get_running_jobs()

    async def set_job_done(self, shot_state: worker.JobState):
        """将job状态设置为已结束(一般由worker设置)"""
        self._py_logger.debug('任务执行结束 完成状态:%s uuid:%s', shot_state.state.name, shot_state.uuid)
        await self._storage.job_log_done(shot_state)

    async def set_job_running(self, log_path: typing.Union[str, pathlib.Path], shot_state: worker.JobState):
        """将job状态设置为运行中(一般由worker设置) 返回log id"""
        self._py_logger.debug('任务开始执行 状态:%s uuid:%s', shot_state.state.name, shot_state.uuid)
        await self._storage.job_log_shoot(log_path, shot_state)

    async def job_check(self):
        """对比trigger storage worker三者的job状态，并进行修正
        启动时会进行一次完成从storage到trigger的载入
        如果job存在于storage不在trigger 则 添加到trigger
        如果job存在于trigger不在storage 则 检查worker状态 并 添加到storage
        """
        self._py_logger.info('尝试检查任务一致性')
        # TODO 检查任务一致性
        pass

    async def log_check(self):
        """检查数据库日志和日志文件一致性，并进行修正
        数据库有日志记录 日志文件不存在时 删除日志记录
        日志文件存在 数据库日志记录不存在时 不做操作
        """
        self._py_logger.info('尝试检查日志一致性')
        # TODO 检查日志一致性
        pass

    async def stop(self):
        self._py_logger.info('尝试停止各项功能 准备结束')
        self.stop_all_trigger()
        self.stop_all_running_jobs()
        await self.job_check()
        await self._storage.stop()

    async def run(self, host: str = '127.0.0.1', port: int = 8000, **kwargs):
        self._py_logger.info('启动fastAPI')
        self._web.on_shutdown(self.stop)
        await self.log_check()
        await self.job_check()
        await self._web.start_server(host, port, **kwargs)
