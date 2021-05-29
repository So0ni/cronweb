import functools
import typing
import pathlib
import asyncio
import datetime
import aiofile
import logger
import cronweb


class AioLogger(logger.LoggerBase):
    def __init__(self, path_log: typing.Union[str, pathlib.Path],
                 controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__(controller)
        self.path_log = pathlib.Path(path_log)
        self.task_dict: typing.Dict[str, asyncio.Task] = {}
        if not self.path_log.exists():
            self.path_log.mkdir(parents=True)

    def get_log_queue(self, uuid: str) -> typing.Tuple[asyncio.queues.Queue, pathlib.Path]:
        self._py_logger.debug('尝试获取执行日志通道 uuid:%s', uuid)
        queue = asyncio.Queue()
        now = datetime.datetime.now()
        file_name = f'{uuid}-{int(now.timestamp() * 1000)}.log'
        path_log_file = self.path_log / file_name
        task = asyncio.create_task(self._log_recording(queue, path_log_file, now))
        task.add_done_callback(functools.partial(self._log_recording_cb, self.task_dict, file_name))
        self.task_dict[file_name] = task
        return queue, path_log_file

    @staticmethod
    def _log_recording_cb(task_dict: typing.Dict[str, asyncio.Task], file_name: str,
                          task: asyncio.Task):
        task_dict.pop(file_name)

    @staticmethod
    async def _log_recording(queue: asyncio.queues.Queue,
                             path_log_file: typing.Union[str, pathlib.Path],
                             now: datetime.datetime) -> None:
        async with aiofile.async_open(str(path_log_file), 'w', encoding='utf8') as afp:
            await afp.write(f'{now}\n')
            while True:
                try:
                    line = await asyncio.wait_for(queue.get(), timeout=1800)
                except asyncio.TimeoutError:
                    break
                if line is logger.LogStop:
                    break
                await afp.write(line)
            await afp.write(f'\n{datetime.datetime.now()}')

        return None
