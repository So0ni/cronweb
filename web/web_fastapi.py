import web
import uvicorn
import fastapi
import fastapi.security
import fastapi.staticfiles
import fastapi.middleware.cors
import pydantic
import cronweb
import typing


class WebFastAPI(web.WebBase):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None,
                 secret: typing.Optional[str] = None,
                 host: typing.Optional[str] = None,
                 port: typing.Optional[int] = None,
                 uv_kwargs: typing.Optional[typing.Dict[str, typing.Any]] = None,
                 fa_kwargs: typing.Optional[typing.Dict[str, typing.Any]] = None):
        super().__init__(controller)
        fa_kwargs = fa_kwargs if fa_kwargs else {}
        self.uv_kwargs = uv_kwargs if uv_kwargs else {}
        self.secret = secret if secret else None
        self.host = host
        self.port = port
        self.app = fastapi.FastAPI(**fa_kwargs)
        self.init_api()

        self.app.add_middleware(
            fastapi.middleware.cors.CORSMiddleware,
            allow_origins=['*'],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def init_api(self):
        self._py_logger.info('初始化fastAPI路由')
        security = fastapi.security.HTTPBearer(auto_error=False)

        class AuthException(Exception):
            def __init__(self, code: int, response: typing.Any):
                self.code = code
                self.response = response

        @self.app.exception_handler(AuthException)
        async def unicorn_exception_handler(request: fastapi.Request,
                                            exc: AuthException):
            return fastapi.responses.JSONResponse(
                status_code=200,
                content={'code': exc.code, 'response': exc.response},
            )

        def check_auth(credentials: fastapi.security.HTTPAuthorizationCredentials = fastapi.Security(security)):
            if self.secret is None:
                return

            if credentials and credentials.scheme.lower() != "bearer":
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_403_FORBIDDEN,
                    detail="无效认证信息",
                )
            if not (credentials and credentials.scheme and credentials.credentials):
                raise AuthException(code=-1, response='未授权，请登录')

            if credentials.credentials != self.secret:
                raise AuthException(code=-2, response='认证信息错误')
            return

        @self.app.get('/api/sys/connection')
        async def connection_check():
            return {'code': 0, 'response': 'hello'}

        @self.app.get('/api/sys/secret')
        async def secret_check(secret: str):
            if self.secret is None and len(secret) != 0:
                return {'code': -1, 'response': '错误的认证信息'}
            if self.secret is not None and self.secret != secret:
                return {'code': -1, 'response': '错误的认证信息'}

            return {'code': 0, 'response': 'hello'}

        @self.app.get('/api/sys/code')
        async def code_explanation():
            return {
                '0': '成功',
                '-1': '未授权，请登录',
                '-2': '认证信息错误',
                '1': '执行失败，查看后台日志',
                '2': '执行失败，查看response'
            }

        class JobInfo(pydantic.BaseModel):
            cron_exp: str
            command: str
            name: str
            param: str = ''

        @self.app.post('/api/job', dependencies=[fastapi.Depends(check_auth)])
        async def add_job(job_info: JobInfo):
            if not self._core.cron_is_valid(job_info.cron_exp):
                return {'response': 'cron表达式无效', 'code': 2}
            job = await self._core.add_job(job_info.cron_exp, job_info.command,
                                           job_info.param, name=job_info.name)
            if not job:
                return {'response': 'failed', 'code': 1}
            return {'response': 'success', 'code': 0}

        @self.app.delete('/api/job/{uuid}', dependencies=[fastapi.Depends(check_auth)])
        async def remove_job(uuid: str):
            job = await self._core.remove_job(uuid)
            if not job:
                return {'response': 'uuid不存在', 'code': 2}
            return {'response': '删除成功', 'code': 0}

        @self.app.post('/api/job/{uuid}/trigger', dependencies=[fastapi.Depends(check_auth)])
        async def trigger_job(uuid: str):
            job = self._core.trigger_job(uuid)
            if not job:
                return {'response': 'uuid不存在', 'code': 2}
            return {'response': '触发成功', 'code': 0}

        class ActiveInfo(pydantic.BaseModel):
            active: int

        @self.app.post('/api/job/{uuid}/active', dependencies=[fastapi.Depends(check_auth)])
        async def update_job_state(uuid: str, act_info: ActiveInfo):
            """active==0为停止 active==1为启动"""
            job = await self._core.update_job_state(uuid, act_info.active)
            if not job:
                return {'response': 'uuid不存在', 'code': 2}
            return {'response': 'active状态更新成功', 'code': 0}

        @self.app.get('/api/jobs', dependencies=[fastapi.Depends(check_auth)])
        async def get_all_jobs():
            """
            {
              "response": [
                {
                  "uuid": "ee5141b095d0426dbd3b375aa00de533",
                  "cron_exp": "*/1 * * * *",
                  "command": "python -c \"import time;time.sleep(30);print('done')\"",
                  "param": "",
                  "name": "睡眠",
                  "date_create": "2021-06-01 00:46:39.090237",
                  "date_update": "2021-06-01 00:46:39.090237"
                }
              ],
              "code": 0
            }
            """
            try:
                jobs = await self._core.get_jobs()
                job_list = [job._asdict() for job in jobs.values()]
                job_list.sort(key=lambda x: x['date_create'])
                return {'response': job_list, 'code': 0}
            except Exception as e:
                self._py_logger.exception(e)
                return {'response': str(e), 'code': 2}

        @self.app.get('/api/running_jobs', dependencies=[fastapi.Depends(check_auth)])
        async def get_all_running_jobs():
            """
            {
              "response": [
                {
                  "shot_id": "acd9575dc42347659c63b4940105b590",
                  "uuid": "ee5141b095d0426dbd3b375aa00de533",
                  "date_start": "2021-06-01 01:18:00.014662"
                }
              ],
              "code": 0
            }
            """
            job_shots = self._core.get_all_running_jobs()
            return {'response': [{'shot_id': shot_id, 'uuid': uuid, 'date_start': date_start}
                                 for shot_id, (uuid, date_start) in job_shots.items()], 'code': 0}

        @self.app.delete('/api/running_jobs/{shot_id}', dependencies=[fastapi.Depends(check_auth)])
        async def stop_running_by_shot_id(shot_id: str):
            result = self._core.stop_running_by_shot_id(shot_id)
            if not result:
                return {'response': '任务未在运行或已运行结束', 'code': 0}
            return {'response': '成功停止运行', 'code': 0}

        @self.app.get('/api/logs', dependencies=[fastapi.Depends(check_auth)])
        async def get_logs_records_undeleted(limit: int = 50):
            """
            {
            "response": [
                {
                  "shot_id": "676389e11bf04195a8c4ac3537b640ac",
                  "uuid": "ee5141b095d0426dbd3b375aa00de533",
                  "state": "DONE",
                  "log_path": "logs\\1622479620020-676389e11bf04195a8c4ac3537b640ac.log",
                  "date_start": "2021-06-01 00:47:00.020000",
                  "date_end": "2021-06-01 00:47:30.067080"
                }
              ],
              "code": 0
            }
            """
            records = await self._core.job_logs_get_undeleted(limit)
            return {'response': [rec._asdict() for rec in records], 'code': 0}

        @self.app.get('/api/job/{uuid}/logs', dependencies=[fastapi.Depends(check_auth)])
        async def get_logs_record_by_uuid(uuid: str):
            """
            {
            "response": [
                {
                  "shot_id": "676389e11bf04195a8c4ac3537b640ac",
                  "uuid": "ee5141b095d0426dbd3b375aa00de533",
                  "state": "DONE",
                  "log_path": "logs\\1622479620020-676389e11bf04195a8c4ac3537b640ac.log",
                  "date_start": "2021-06-01 00:47:00.020000",
                  "date_end": "2021-06-01 00:47:30.067080"
                }
              ],
              "code": 0
            }
            """
            records = await self._core.job_logs_get_by_uuid(uuid)
            return {'response': [rec._asdict() for rec in records], 'code': 0}

        @self.app.get('/api/log/{shot_id}',
                      dependencies=[fastapi.Depends(check_auth)],
                      response_class=fastapi.responses.PlainTextResponse)
        async def get_log_by_shot_id(shot_id: str):
            log_record = await self._core.job_log_get_by_shot_id(shot_id)
            if not log_record:
                return '日志不存在'
            return log_record

        self.app.mount("/", fastapi.staticfiles.StaticFiles(directory="static", html=True), name="site")

    def on_shutdown(self, func: typing.Callable):
        self._py_logger.info('添加fastAPI shutdown回调')
        self.app.on_event('shutdown')(func)

    async def start_server(self, host: typing.Optional[str] = None,
                           port: typing.Optional[int] = None, **kwargs):
        host = host or self.host or '127.0.0.1'
        port = port or self.port or 8000
        uv_kwargs = self.uv_kwargs.copy()
        uv_kwargs.update(kwargs)
        client_cert = uv_kwargs.pop('client_cert', None)
        if client_cert:
            if 'ssl_keyfile' not in uv_kwargs or \
                    'ssl_certfile' not in uv_kwargs or \
                    'ssl_ca_certs' not in uv_kwargs:
                raise IOError('启用客户端证书验证需要配置服务端证书和用户证书的可信CA')
            import ssl
            uv_kwargs['ssl_cert_reqs'] = ssl.CERT_REQUIRED

        config = uvicorn.Config(self.app, host, port, workers=1, **uv_kwargs)
        server = uvicorn.Server(config)
        return await server.serve()
