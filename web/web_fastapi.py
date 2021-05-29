import web
import uvicorn
import fastapi
import cronweb
import typing


class WebFastAPI(web.WebBase):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None,
                 fa_kwargs: typing.Optional[typing.Dict[str, typing.Any]] = None):
        super().__init__(controller)
        fa_kwargs = fa_kwargs if fa_kwargs else {}
        self.app = fastapi.FastAPI(**fa_kwargs)
        self.init_api()

    def init_api(self):
        self._py_logger.info('初始化fastAPI路由')

        @self.app.get('/')
        async def index():
            return {'response': 'hello'}

        @self.app.get('/code')
        async def code_exp():
            return {
                '0': '成功',
                '-1': '未授权，请登录',
                '1': '执行失败，查看后台日志',
                '2': '执行失败，查看response'
            }

        # TODO 完成API设计

        @self.app.post('/job')
        async def add_job(cron_exp: str, command: str, param: str, name: str):
            job = await self._core.add_job(cron_exp, command, param, name=name)
            if not job:
                return {'response': 'failed', 'code': 0}
            return {'response': 'success', 'code': 0}

        @self.app.delete('/job/{uuid}')
        async def remove_job(uuid: str):
            job = await self._core.remove_job(uuid)
            if not job:
                return {'response': 'uuid不存在', 'code': 2}
            return {'response': '删除成功', 'code': 0}

        @self.app.get('/jobs')
        async def get_all_jobs():
            try:
                jobs = await self._core.get_jobs()
                return {'response': [tuple(job) for job in jobs.values()], 'code': 0}
            except Exception as e:
                self._py_logger.exception(e)
                return {'response': str(e), 'code': 2}

        @self.app.get('/running_jobs')
        async def get_all_running_jobs():
            jobs_uuid = self._core.get_all_running_jobs()
            return {'response': list(jobs_uuid), 'code': 0}

    def on_shutdown(self, func: typing.Callable):
        self._py_logger.info('添加fastAPI shutdown回调')
        self.app.on_event('shutdown')(func)

    async def start_server(self, host: str = '127.0.0.1', port: int = 8000, **kwargs):
        config = uvicorn.Config(self.app, host, port, workers=1, **kwargs)
        server = uvicorn.Server(config)
        return await server.serve()
