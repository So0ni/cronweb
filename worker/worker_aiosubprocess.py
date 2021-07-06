import concurrent.futures
import logging
import os
import json
import pathlib
import asyncio
import datetime
import typing
import worker
import cronweb
import logger
import locale
import hmac
import base64
import aiohttp
import asyncio.subprocess
import threading
from uuid import uuid4


class EventLoopThreadStopError(Exception):
    pass


class HookEventLoopThread(threading.Thread):
    def __init__(self, *args,
                 loop_main: typing.Optional[asyncio.AbstractEventLoop] = None,
                 loop_child: typing.Optional[asyncio.AbstractEventLoop] = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.loop_main = loop_main or asyncio.get_event_loop()
        self.loop_child = loop_child or asyncio.new_event_loop()
        self.running = False
        self.running_futures: typing.Set[asyncio.Future] = set()
        self._py_logger = logging.getLogger('cronweb.worker.HookEventLoopThread')

    def run(self):
        self.running = True
        self.loop_child.run_forever()

    def _callback_done(self, future: asyncio.Future):
        self.running_futures.remove(future)
        try:
            future.exception()
        except (asyncio.CancelledError, concurrent.futures.CancelledError):
            pass
        self._py_logger.debug('hook执行结束')

    async def _timeout_wrap(self, coroutine: typing.Awaitable, timeout: float):
        try:
            await asyncio.wait_for(coroutine, timeout)
        except asyncio.TimeoutError as e:
            self._py_logger.warning('hook执行超时')
            self._py_logger.exception(e)

    def run_coroutine(self, coroutine, timeout: float) -> asyncio.Future:
        if not self.running:
            raise EventLoopThreadStopError('hook事件循环线程已停止')
        future_concurrent = asyncio.run_coroutine_threadsafe(
            self._timeout_wrap(coroutine, timeout=timeout),
            loop=self.loop_child
        )
        future_asyncio = asyncio.wrap_future(future_concurrent, loop=self.loop_main)
        future_asyncio.add_done_callback(self._callback_done)
        self.running_futures.add(future_asyncio)
        return future_asyncio

    def stop(self):
        self._py_logger.debug('hook事件循环停止运行')
        self.running = False
        [fu.cancel() for fu in self.running_futures]
        self.loop_child.call_soon_threadsafe(self.loop_child.stop)
        self.join()


class AioSubprocessWorker(worker.WorkerBase):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None,
                 work_dir: typing.Optional[typing.Union[str, pathlib.Path]] = None,
                 times_retry: int = 2, wait_retry_base=30,
                 webhook_url: str = '',
                 webhook_secret: str = ''):
        super().__init__(controller)
        self._running_jobs: typing.Dict[str, typing.Tuple[str, asyncio.subprocess.Process, worker.JobState]] = {}
        self._env: typing.Optional[typing.Dict[str, str]] = None
        self._scripts_dir: typing.Optional[typing.Union[str, pathlib.Path]] = None
        self._work_dir = pathlib.Path(work_dir).absolute() if work_dir else None
        self.times_retry = times_retry
        self.wait_retry_base = wait_retry_base
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret if isinstance(webhook_secret, bytes) else webhook_secret.encode('utf8')
        self.webhook_timeout = aiohttp.ClientTimeout(total=30)
        self._hook_thread = HookEventLoopThread()
        self._hook_thread.start()

        self._killed_shot_id: typing.Set[str] = set()
        self._waiting_for_retry: typing.Set[str] = set()
        if self._work_dir is not None and not self._work_dir.exists():
            self._work_dir.mkdir(parents=True)

        if self._core is not None:
            self.load_env()

    def load_env(self):
        self._py_logger.info('trigger载入子进程环境变量')
        file_env = self._core.dir_project / '.env_subprocess.json'
        if file_env.exists():
            self._py_logger.info('.env_subprocess.json文件存在，读取其中内容作为环境变量')
            with open(file_env, 'r', encoding='utf8') as fp:
                self._env = json.load(fp)
        else:
            self._py_logger.info('.env_subprocess.json文件不存在，使用默认环境变量')
            self._env = dict(os.environ)

        if self._work_dir is None:
            self._work_dir = pathlib.Path(self._core.dir_project / 'scripts').absolute()
            if not self._work_dir.exists():
                self._work_dir.mkdir(parents=True)

    async def _shoot(self, command: str, param: str,
                     uuid: str, timeout: float, job_type: worker.JobTypeEnum) -> typing.Tuple[str, worker.JobStateEnum]:
        if self._env is None:
            self.load_env()
        shot_id = uuid4().hex
        self._py_logger.debug('执行启动 uuid:%s command:%s param:%s', uuid, command, param)

        proc = await asyncio.create_subprocess_shell(
            # 只有当param存在时传入param参数(用于传递特殊参数 约定后可以是json)
            f'{command} --param {param}' if param else command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=self._env,
            cwd=str(self._work_dir)
        )
        now = datetime.datetime.now()
        queue, log_path = self._core.get_log_queue(uuid, shot_id, timeout)
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
                    if exit_code == 0:
                        state_proc = worker.JobStateEnum.DONE
                        self._py_logger.debug('任务完成 shot_id:%s', shot_id)
                        await queue.put('\nJob DONE')
                    elif shot_id in self._killed_shot_id:
                        self._killed_shot_id.remove(shot_id)
                        state_proc = worker.JobStateEnum.KILLED
                        self._py_logger.debug('手动停止 ExitCode:%s shot_id:%s', exit_code, shot_id)
                        await queue.put('\nJob KILLED')
                    else:
                        state_proc = worker.JobStateEnum.ERROR
                        self._py_logger.debug('任务失败 ExitCode:%s shot_id:%s', exit_code, shot_id)
                        await queue.put('\nJob FAILED')
                    # 停止日志记录
                    await queue.put(logger.LogStop)
                    break
                await queue.put(f'{line.decode(default_encoding).rstrip()}\n')
            except asyncio.TimeoutError:
                self._py_logger.error('等待stdout %ss超时 shot_id:%s', timeout, shot_id)
                await queue.put(f'\n#### OUTPUT END ####\n\nKilled Timeout {timeout}s\nJob TIMEOUT')
                await queue.put(logger.LogStop)
                proc.kill()
                self._py_logger.error('任务超时 killed shot_id:%s', shot_id)
                state_proc = worker.JobStateEnum.KILLED
                break
        end = datetime.datetime.now()
        await self._core.set_job_done(worker.JobState(uuid, state_proc, shot_id, str(now), str(end)))
        self._running_jobs.pop(shot_id)
        return shot_id, state_proc

    async def shoot(self, command: str, param: str, uuid: str, timeout: float, name: str,
                    job_type: worker.JobTypeEnum) -> None:
        is_retry = False
        shot_id_root: typing.Optional[str] = None
        hook_futures: typing.List[asyncio.Future] = []
        hook_timeout = 30
        for count_shoot in range(self.times_retry + 1):
            if is_retry:
                wait_seconds = ((2 ** count_shoot) - 1) * self.wait_retry_base
                self._py_logger.debug('等待%s秒后开始第%s次重试 共%s次重试',
                                      wait_seconds, count_shoot, self.times_retry)
                job_type = worker.JobTypeEnum.RETRY
                await asyncio.sleep(wait_seconds)
            shot_id, state = await self._shoot(command, param, uuid, timeout, job_type)

            # 优先webhook
            if self.webhook_url:
                hook_futures.append(
                    self._hook_thread.run_coroutine(
                        self._webhook_job_done(name, shot_id, state, job_type),
                        timeout=hook_timeout
                    )
                )
            # 其后本地hook 为避免影响重试机制使用task交给loop执行
            for func in self._job_done_hooks:
                hook_futures.append(
                    self._hook_thread.run_coroutine(func(name, shot_id, state, job_type), timeout=hook_timeout)
                )

            if state.name != 'ERROR':
                break
            elif not is_retry:
                self._py_logger.warning('初次运行失败 启动重试 shot_id: %s', shot_id)
                is_retry = True
                shot_id_root = shot_id
                self._waiting_for_retry.add(shot_id_root)
        # 不管是运行成功 重试后成功 还是超出重试次数 都要检查
        if shot_id_root and shot_id_root in self._waiting_for_retry:
            self._py_logger.warning('移除等待重试集合 shot_id: %s', shot_id_root)
            self._waiting_for_retry.remove(shot_id_root)

        return None

    def _webhook_sign(self, payload: bytes) -> str:
        sign_bytes = hmac.new(self.webhook_secret, payload, 'sha256').digest()
        sign = base64.b64encode(sign_bytes).decode()
        return sign

    async def _webhook_job_done(self, name: str, shot_id: str, state: worker.JobStateEnum,
                                job_type: worker.JobTypeEnum) -> None:
        if not self.webhook_url:
            return None
        self._py_logger.info('触发任务结束webhook')
        payload_dict = {
            'name': name,
            'shot_id': shot_id,
            'state': state.name,
            'job_type': job_type.name,
            'timestamp': int(datetime.datetime.now().timestamp() * 1000)
        }
        payload = json.dumps(payload_dict, ensure_ascii=False).encode('utf8')
        sign = self._webhook_sign(payload)
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'CronWeb/Webhook',
            'Content-Type': 'application/json; charset=UTF-8',
            'X-Cronweb-Token': sign,
            'X-Cronweb-Timestamp': f'{payload_dict["timestamp"]}'
        }

        async with aiohttp.ClientSession(timeout=self.webhook_timeout) as session:
            try:
                resp = await session.post(self.webhook_url, data=payload, headers=headers)
                resp.close()
            except Exception as e:
                self._py_logger.error('webhook调用失败')
                self._py_logger.exception(e)
        self._py_logger.info('webhook结束')

    def get_running_jobs(self) -> typing.Dict[str, typing.Tuple[str, str]]:
        """返回worker中正在运行任务的所有信息
        {shot_id: (uuid, date_start)}
        """
        self._py_logger.debug('获取worker中所有运行中任务')
        running = {shot_id: (value[0], value[2].date_start)
                   for shot_id, value in self._running_jobs.items()}
        self._py_logger.info('%s个正在运行的任务', len(running))
        return running

    async def kill_all_running_jobs(self) -> typing.Dict[str, str]:
        """关闭所有正在运行的任务 返回关闭成功的信息
        {shot_id: uuid}
        """
        self._py_logger.info('停止worker中所有正在运行任务')
        success_dict = {}
        for key, job in self._running_jobs.items():
            try:
                await self.kill_by_shot_id(key)
                success_dict[key] = job[0]
            except Exception as e:
                self._py_logger.exception(e)
        self._py_logger.info('已停止%s个正在运行的任务', len(success_dict))
        return success_dict

    async def kill_by_shot_id(self, shot_id: str) -> typing.Optional[str]:
        self._py_logger.info('停止worker中正在运行任务 shot_id:%s', shot_id)
        if shot_id not in self:
            return None
        job = self._running_jobs[shot_id]
        self._killed_shot_id.add(shot_id)
        job[1].terminate()
        try:
            await asyncio.wait_for(job[1].wait(), timeout=5)
        except asyncio.TimeoutError:
            self._py_logger.warning('子进程正常中止超时 尝试强制停止')
            job[1].kill()
        return shot_id

    def stop(self):
        self._hook_thread.stop()

    def __contains__(self, shot_id: str) -> bool:
        return shot_id in self._running_jobs
