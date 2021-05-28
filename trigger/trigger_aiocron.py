import trigger
import aiocron
import typing
from uuid import uuid4

import cronweb


class CronJob(typing.NamedTuple):
    # Cron instance has uuid
    cron: aiocron.Cron
    command: str
    param: str
    name: str


class TriggerAioCron(trigger.TriggerBase):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__(controller)
        self._job_dict: typing.Dict[str, CronJob] = {}

    def add_job(self, cron_exp: str, command: str, param: str,
                uuid: typing.Optional[str] = None, name: str = '',
                update: bool = True) -> typing.Optional[trigger.JobInfo]:
        if uuid is None:
            uuid = uuid4().hex
        elif uuid in self:
            if update is not True:
                raise trigger.JobDuplicateError(f'job {uuid} has been exists')
            return self.update_job(uuid, cron_exp, command, param, name)

        async def job_func(core_inner: cronweb.CronWeb,
                           command_inner: str, param_inner: str):
            await core_inner.shoot(command_inner, param_inner, uuid)

        cron = aiocron.Cron(spec=cron_exp,
                            func=job_func,
                            args=(self._core, command, param),
                            start=True,
                            uuid=uuid
                            )
        self._job_dict[uuid] = CronJob(cron, command, param, name)
        return self._cronjob_to_jobinfo(self._job_dict[uuid])

    def update_job(self, uuid: str, cron_exp: str, command: str, param: str,
                   name: str = '') -> typing.Optional[trigger.JobInfo]:
        if uuid not in self:
            return None
        self.remove_job(uuid)
        return self.add_job(cron_exp, command, param, uuid, name)

    def remove_job(self, uuid: str) -> typing.Optional[trigger.JobInfo]:
        if uuid not in self:
            return None
        job = self._job_dict.pop(uuid)
        job.cron.stop()
        return self._cronjob_to_jobinfo(job)

    def get_jobs(self) -> typing.Dict[str, trigger.JobInfo]:
        return {uuid: self._cronjob_to_jobinfo(cronjob)
                for uuid, cronjob in self._job_dict.items()}

    def stop_all(self) -> typing.Dict[str, trigger.JobInfo]:
        for job in self._job_dict.values():
            job.cron.stop()
        return {uuid: self._cronjob_to_jobinfo(cronjob)
                for uuid, cronjob in self._job_dict.items()}

    @staticmethod
    def _cronjob_to_jobinfo(job: CronJob) -> trigger.JobInfo:
        return trigger.JobInfo(job.cron.uuid, job.cron.spec, job.command, job.param, job.name)

    def __contains__(self, uuid: str) -> bool:
        return uuid in self._job_dict
