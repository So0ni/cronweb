import asyncio
import datetime
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
        self._running_jobs: typing.Dict[str, typing.Tuple[str, asyncio.subprocess.Process, worker.JobState]] = {}

    async def shoot(self, command: str, param: str, uuid: str, timeout: float) -> None:
        shot_id = uuid4().hex
        self._py_logger.debug('执行启动 uuid:%s command:%s param:%s', uuid, command, param)
        proc = await asyncio.create_subprocess_shell(
            # 只有当param存在时传入param参数(用于传递特殊参数 约定后可以是json)
            f'{command} --param {param}' if param else command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        now = datetime.datetime.now()
        queue, log_path = self._core.get_log_queue(uuid, shot_id)
        state_proc = worker.JobStateEnum.RUNNING
        job_state = worker.JobState(uuid, state_proc, shot_id, str(now))
        await self._core.set_job_running(log_path, job_state)
        self._running_jobs[shot_id] = (uuid, proc, job_state)
        await queue.put(f'shot_id: {shot_id}\nuuid: {uuid}\n'
                        f'command: {command}\nparam: {param}\n\n#### OUTPUT ####\n')
        default_encoding = locale.getpreferredencoding()
        while True:
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout)
                if not line:
                    # test?进程运行结束时自动关闭管道并发送EOF？如果不是wait会导致可能的死锁
                    exit_code = await proc.wait()
                    await queue.put(f'\n#### OUTPUT END ####\n\nExit Code: {exit_code}')
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
        end = datetime.datetime.now()
        await self._core.set_job_done(worker.JobState(uuid, state_proc, shot_id, str(now), str(end)))
        self._running_jobs.pop(shot_id)
        return

    def get_running_jobs(self) -> typing.Dict[str, typing.Tuple[str, str]]:
        """返回worker中正在运行任务的所有{shot_id: (uuid, date_start)}"""
        self._py_logger.debug('获取worker中所有运行中任务')
        running = {shot_id: (value[0], value[2].date_start)
                   for shot_id, value in self._running_jobs.items()}
        self._py_logger.info('%s个正在运行的任务', len(running))
        return running

    def kill_all_running_jobs(self) -> typing.Dict[str, str]:
        """关闭所有正在运行的任务 返回关闭成功的"""
        self._py_logger.info('停止worker中所有正在运行任务')
        success_dict = {}
        for key, job in self._running_jobs.items():
            try:
                job[1].kill()
                success_dict[key] = job[0]
            except Exception:
                pass
        self._py_logger.info('已停止%s个正在运行的任务', len(success_dict))
        return success_dict

    def kill_by_shot_id(self, shot_id: str) -> typing.Optional[str]:
        self._py_logger.info('停止worker中正在运行任务 shot_id:%s', shot_id)
        if shot_id not in self:
            return None
        self._running_jobs[shot_id][1].kill()
        return shot_id

    def __contains__(self, shot_id: str) -> bool:
        return shot_id in self._running_jobs
