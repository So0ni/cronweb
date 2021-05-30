import trigger
import aiocron
import typing
import datetime
import asyncio
from uuid import uuid4
import croniter
import cronweb


class CronJob(typing.NamedTuple):
    # Cron instance has uuid
    cron: aiocron.Cron
    command: str
    param: str
    name: str
    date_create: str
    date_update: str


class TriggerAioCron(trigger.TriggerBase):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__(controller)
        self._job_dict: typing.Dict[str, CronJob] = {}

    def add_job(self, cron_exp: str, command: str, param: str,
                date_create: str, date_update: typing.Optional[str] = None,
                uuid: typing.Optional[str] = None, name: str = '',
                update: bool = True) -> typing.Optional[trigger.JobInfo]:
        self._py_logger.info('尝试新建job 任务名:%s', name)
        self._py_logger.debug('job 周期:%s 命令:%s', cron_exp, command)
        if uuid is None:
            uuid = uuid4().hex
            self._py_logger.debug('未指定uuid 自动生成:%s', uuid)
        elif uuid in self:
            if update is not True:
                raise trigger.JobDuplicateError(f'job {uuid} has been exists')
            self._py_logger.warning('任务uuid:%s 任务名:%s 已存在 尝试更新', uuid, name)
            date_update = date_update or str(datetime.datetime.now())
            return self.update_job(uuid, cron_exp, command, param, date_update, name)

        def job_func(core_inner: cronweb.CronWeb,
                     command_inner: str, param_inner: str):
            return asyncio.ensure_future(core_inner.shoot(command_inner, param_inner, uuid))

        cron = aiocron.Cron(spec=cron_exp,
                            func=job_func,
                            args=(self._core, command, param),
                            start=True,
                            uuid=uuid
                            )
        self._job_dict[uuid] = CronJob(cron, command, param, name, date_create, date_update or date_create)
        return self._cronjob_to_jobinfo(self._job_dict[uuid])

    def update_job(self, uuid: str, cron_exp: str, command: str, param: str,
                   date_update: str,
                   name: str = '') -> typing.Optional[trigger.JobInfo]:
        self._py_logger.info('尝试更新trigger任务 %s', uuid)
        if uuid not in self:
            self._py_logger.warning('uuid不存在于trigger 不可更新: %s', uuid)
            return None
        date_create = self.remove_job(uuid).date_create
        return self.add_job(cron_exp, command, param, date_create, date_update, uuid, name, update=False)

    def remove_job(self, uuid: str) -> typing.Optional[trigger.JobInfo]:
        self._py_logger.info('尝试从trigger删除任务 %s', uuid)
        if uuid not in self:
            self._py_logger.warning('uuid不存在于trigger 不可删除: %s', uuid)
            return None
        job = self._job_dict.pop(uuid)
        self._py_logger.debug('从trigger中停止任务')
        job.cron.stop()
        return self._cronjob_to_jobinfo(job)

    def get_jobs(self) -> typing.Dict[str, trigger.JobInfo]:
        self._py_logger.debug('从trigger中获取所有任务')
        return {uuid: self._cronjob_to_jobinfo(cronjob)
                for uuid, cronjob in self._job_dict.items()}

    def stop_all(self) -> typing.Dict[str, trigger.JobInfo]:
        self._py_logger.info('尝试停止trigger中所有任务')
        for job in self._job_dict.values():
            job.cron.stop()
        return {uuid: self._cronjob_to_jobinfo(cronjob)
                for uuid, cronjob in self._job_dict.items()}

    @staticmethod
    def cron_is_valid(cron_exp: str) -> bool:
        return croniter.croniter.is_valid(cron_exp)

    @staticmethod
    def _cronjob_to_jobinfo(job: CronJob) -> trigger.JobInfo:
        return trigger.JobInfo(job.cron.uuid, job.cron.spec, job.command,
                               job.param, job.name, job.date_create, job.date_update)

    def __contains__(self, uuid: str) -> bool:
        return uuid in self._job_dict
