import storage
import trigger
import worker
import web
import logger
import typing
import asyncio


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
        return await self._worker.shoot(command, param, uuid, timeout)

    def add_job(self, cron_exp: str, command: str, param: str,
                uuid: typing.Optional[str] = None, name: str = '') -> trigger.JobInfo:
        job = self._trigger.add_job(cron_exp, command, param, uuid, name)
        if job is not None:
            pass
        # TODO 添加写数据库等行为
        return job

    def update_job(self, uuid: str, cron_exp: str, command: str, param: str,
                   name: str = '') -> typing.Optional[trigger.JobInfo]:
        job = self._trigger.update_job(cron_exp, command, param, uuid, name)
        if job is not None:
            pass
        # TODO 添加写数据库等行为
        return job

    def remove_job(self, uuid: str) -> typing.Optional[trigger.JobInfo]:
        job = self._trigger.remove_job(uuid)
        if job is not None:
            pass
        # TODO 添加写数据库等行为
        return job

    def get_jobs(self) -> typing.Dict[str, trigger.JobInfo]:
        # TODO 考虑从storage里取还是trigger里取
        return self._trigger.get_jobs()

    def get_log_queue(self, uuid: str) -> asyncio.queues.Queue:
        return self._aiolog.get_log_queue(uuid)

    def stop_all_running_jobs(self) -> typing.Set[str]:
        # TODO done?主进程接收到停止命令时需要
        return self._worker.kill_all_running_jobs()

    def get_all_running_jobs(self) -> typing.Set[str]:
        # TODO done?获取正在运行的job
        return self._worker.get_running_jobs()

    def job_done(self, uuid: str, state: worker.JobState):
        # TODO 任务完成时写入数据库
        pass

    def job_running(self, uuid: str, state: worker.JobState):
        # TODO 任务开始运行时写入数据库
        pass

    async def run(self, host: str = '127.0.0.1', port: int = 8000, **kwargs):
        await self._web.start_server(host, port, **kwargs)
