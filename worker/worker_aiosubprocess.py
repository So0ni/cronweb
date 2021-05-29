import asyncio
import typing
import worker
import cronweb
import logger
import asyncio.subprocess


class AioSubprocessWorker(worker.WorkerBase):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__(controller)
        self._running_jobs: typing.Dict[str, asyncio.subprocess.Process] = {}

    async def shoot(self, command: str, param: str, uuid: str, timeout: float) -> None:
        self._py_logger.debug('执行启动 uuid:%s command:%s param:%s', uuid, command, param)
        proc = await asyncio.create_subprocess_shell(
            # 只有当param存在时传入param参数(用于传递特殊参数 约定后可以是json)
            f'{command} --param {param}' if param else command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        queue, log_path = self._core.get_log_queue(uuid)
        state_proc = worker.JobStateEnum.RUNNING
        log_id = await self._core.set_job_running(uuid, log_path, worker.JobState(uuid, state_proc))
        self._running_jobs[uuid] = proc
        await queue.put(f'uuid: {uuid}\ncommand: {command}\nparam: {param}')
        while True:
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout)
                if not line:
                    # TODO test?进程运行结束时自动关闭管道并发送EOF？如果不是wait会导致可能的死锁
                    exit_code = await proc.wait()
                    await queue.put(f'Exit Code {exit_code}\n')
                    await queue.put(logger.LogStop)
                    if exit_code == 0:
                        state_proc = worker.JobStateEnum.DONE
                        self._py_logger.debug('任务完成 %s', uuid)
                    else:
                        state_proc = worker.JobStateEnum.ERROR
                        self._py_logger.debug('任务失败 ExitCode:%s %s', exit_code, uuid)
                    break
                await queue.put(line)
            except asyncio.TimeoutError:
                self._py_logger.error('等待stdout %ss超时 %s', timeout, uuid)
                await queue.put(f'Killed Timeout {timeout}s')
                await queue.put(logger.LogStop)
                proc.kill()
                self._py_logger.error('任务killed %s', uuid)
                state_proc = worker.JobStateEnum.KILLED
                break
        await self._core.set_job_done(log_id, worker.JobState(uuid, state_proc))
        self._running_jobs.pop(uuid)
        return

    def get_running_jobs(self) -> typing.Set[str]:
        self._py_logger.debug('获取worker中所有运行中任务')
        return set(self._running_jobs.keys())

    def kill_all_running_jobs(self) -> typing.Set[str]:
        self._py_logger.info('尝试停止worker中所有正在运行任务')
        success_set = set()
        for key, job in self._running_jobs.items():
            try:
                job.kill()
                success_set.add(key)
            except Exception:
                pass
        return success_set
