import asyncio
import typing
import worker
import cronweb
import logger
import locale
import asyncio.subprocess
from uuid import uuid4


class AioSubprocessWorker(worker.WorkerBase):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__(controller)
        self._running_jobs: typing.Dict[str, typing.Tuple[str, asyncio.subprocess.Process]] = {}

    async def shoot(self, command: str, param: str, uuid: str, timeout: float) -> None:
        shot_id = uuid4().hex
        self._py_logger.debug('执行启动 uuid:%s command:%s param:%s', uuid, command, param)
        proc = await asyncio.create_subprocess_shell(
            # 只有当param存在时传入param参数(用于传递特殊参数 约定后可以是json)
            f'{command} --param {param}' if param else command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        queue, log_path = self._core.get_log_queue(uuid, shot_id)
        state_proc = worker.JobStateEnum.RUNNING
        await self._core.set_job_running(log_path, worker.JobState(uuid, state_proc, shot_id))
        self._running_jobs[shot_id] = (uuid, proc)
        await queue.put(f'shot_id:{shot_id}\nuuid: {uuid}\ncommand: {command}\nparam: {param}\n####OUTPUT####\n')
        default_encoding = locale.getpreferredencoding()
        while True:
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout)
                if not line:
                    # TODO test?进程运行结束时自动关闭管道并发送EOF？如果不是wait会导致可能的死锁
                    exit_code = await proc.wait()
                    await queue.put(f'\n####OUTPUT END####\nExit Code {exit_code}')
                    await queue.put(logger.LogStop)
                    if exit_code == 0:
                        state_proc = worker.JobStateEnum.DONE
                        self._py_logger.debug('任务完成 shot_id:%s', shot_id)
                    else:
                        state_proc = worker.JobStateEnum.ERROR
                        self._py_logger.debug('任务失败 ExitCode:%s shot_id:%s', exit_code, shot_id)
                    break
                await queue.put(line.decode(default_encoding))
            except asyncio.TimeoutError:
                self._py_logger.error('等待stdout %ss超时 shot_id:%s', timeout, shot_id)
                await queue.put(f'Killed Timeout {timeout}s')
                await queue.put(logger.LogStop)
                proc.kill()
                self._py_logger.error('任务超时 killed shot_id:%s', shot_id)
                state_proc = worker.JobStateEnum.KILLED
                break
        await self._core.set_job_done(worker.JobState(uuid, state_proc, shot_id))
        self._running_jobs.pop(shot_id)
        return

    def get_running_jobs(self) -> typing.Dict[str, str]:
        """返回worker中正在运行任务的所有{shot_id: uuid}"""
        self._py_logger.debug('获取worker中所有运行中任务')
        return {shot_id: value[0] for shot_id, value in self._running_jobs.items()}

    def kill_all_running_jobs(self) -> typing.Dict[str, str]:
        """关闭所有正在运行的任务 返回关闭成功的"""
        self._py_logger.info('尝试停止worker中所有正在运行任务')
        success_dict = {}
        for key, job in self._running_jobs.items():
            try:
                job[1].kill()
                success_dict[key] = job[0]
            except Exception:
                pass
        return success_dict

    def kill_by_shot_id(self, shot_id: str) -> typing.Optional[str]:
        self._py_logger.info('尝试停止worker中正在运行任务 shot_id:%s', shot_id)
        if shot_id not in self:
            return None
        self._running_jobs[shot_id][1].kill()
        return shot_id

    def __contains__(self, shot_id: str) -> bool:
        return shot_id in self._running_jobs
