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
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        queue = self._core.get_log_queue(uuid)
        state_proc = worker.JobStateEnum.RUNNING
        self._core.job_running(uuid, worker.JobState(uuid, state_proc))
        self._running_jobs[uuid] = proc

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
                    else:
                        state_proc = worker.JobStateEnum.ERROR
                    break
                await queue.put(line)
            except asyncio.TimeoutError:
                await queue.put(f'Killed Timeout {timeout}s')
                await queue.put(logger.LogStop)
                proc.kill()
                state_proc = worker.JobStateEnum.KILLED
                break
        self._core.job_done(uuid, worker.JobState(uuid, state_proc))
        self._running_jobs.pop(uuid)
        return

    def get_running_jobs(self) -> typing.Set[str]:
        return set(self._running_jobs.keys())

    def kill_all_running_jobs(self) -> typing.Set[str]:
        success_set = set()
        for key, job in self._running_jobs.items():
            try:
                job.kill()
                success_set.add(key)
            except Exception:
                pass
        return success_set
