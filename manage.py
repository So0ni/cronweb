# CronWeb and CronWeb-front
# Copyright (C) 2021. Sonic Young.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import asyncio
import pathlib
import argparse
import logging
import cronweb
import yaml
import typing

_py_logger = logging.getLogger('cronweb.manage')


def load_config(path_config: typing.Optional[typing.Union[str, pathlib.Path]] = None) -> typing.Dict[str, typing.Any]:
    path_config = pathlib.Path(path_config) if path_config else pathlib.Path(__file__).parent / 'config.yaml'
    if not path_config.exists():
        raise IOError(f'配置文件{path_config}不存在')
    with open(path_config, 'r', encoding='utf8') as fp:
        config = yaml.load(fp, Loader=yaml.SafeLoader)
        return config


def load_hooks(core: cronweb.CronWeb):
    import importlib
    import inspect
    dir_hooks = core.dir_project / 'hooks'
    hook_files = dir_hooks.glob('hook_*.py')
    for hook_file in hook_files:
        _py_logger.info('发现hook代码文件 %s', hook_file.stem)
        hook_module = importlib.import_module(f'hooks.{hook_file.stem}')
        names_func = [name for name in dir(hook_module) if name.startswith('hook_job_done')]
        if not names_func:
            _py_logger.warning('hook代码文件中没有hook_job_done开头的函数名 跳过')
            continue
        for name in names_func:
            func = getattr(hook_module, name)
            if not inspect.iscoroutinefunction(func):
                _py_logger.warning('函数 %s 并非有效的异步函数 跳过', name)
                continue
            _py_logger.warning('注册函数 %s', name)
            core.add_job_done_hook(func)


async def init(config: typing.Dict[str, typing.Any]) -> cronweb.CronWeb:
    import logger.logger_aio
    import storage.storage_aiosqlite
    import trigger.trigger_aiocron
    import web.web_fastapi
    import worker.worker_aiosubprocess
    core = await cronweb.CronWeb.create_from_config(
        config,
        logger.logger_aio.AioLogger,
        trigger.trigger_aiocron.TriggerAioCron,
        web.web_fastapi.WebFastAPI,
        worker.worker_aiosubprocess.AioSubprocessWorker,
        storage.storage_aiosqlite.AioSqliteStorage.create
    )
    return core


async def main(path_config: typing.Optional[typing.Union[str, pathlib.Path]] = None):
    config = load_config(path_config)
    core = await init(config)
    load_hooks(core)
    await core.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CronWeb操作工具')
    parser.add_argument('command', type=str, help='启动CronWeb', nargs='?',
                        choices=['run']
                        )
    parser.add_argument('-c', '--config', dest='path_config', default=None, nargs='?', help='指定配置文件路径')
    args = parser.parse_args()

    if args.command == 'run':
        asyncio.run(main(args.path_config))
