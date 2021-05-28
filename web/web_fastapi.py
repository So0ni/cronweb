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
        @self.app.get('/')
        def index():
            return {'response': 'hello'}
        # TODO 完成API设计

    def on_shutdown(self, func: typing.Callable):
        self.app.on_event('shutdown')(func)

    async def start_server(self, host: str = '127.0.0.1', port: int = 8000, **kwargs):
        config = uvicorn.Config(self.app, host, port, workers=1, **kwargs)
        server = uvicorn.Server(config)
        return await server.serve()
