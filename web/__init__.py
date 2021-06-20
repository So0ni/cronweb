from __future__ import annotations
import abc
import typing
import logging

if typing.TYPE_CHECKING:
    import cronweb


class WebBase(abc.ABC):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None, **kwargs):
        super().__init__()
        self._core: typing.Optional[cronweb.CronWeb] = controller
        self._py_logger: logging.Logger = logging.getLogger(f'cronweb.{self.__class__.__name__}')
        self.controller_default()

    def set_controller(self, controller: cronweb.CronWeb):
        self._core = controller

    def controller_default(self):
        if self._core is not None:
            self._core.set_web_default(self)

    @abc.abstractmethod
    def on_shutdown(self, func: typing.Callable):
        pass

    @abc.abstractmethod
    async def start_server(self, host: str = '127.0.0.1', port: int = 8000, **kwargs):
        pass
