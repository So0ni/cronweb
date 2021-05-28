from __future__ import annotations
import abc
import typing

if typing.TYPE_CHECKING:
    import cronweb


class WebBase(abc.ABC):
    def __init__(self, controller: typing.Optional[cronweb.CronWeb] = None):
        super().__init__()
        self._core: typing.Optional[cronweb.CronWeb] = controller

    def set_controller(self, controller: cronweb.CronWeb):
        self._core = controller

    @abc.abstractmethod
    async def start_server(self, host: str = '127.0.0.1', port: int = 8000, **kwargs):
        pass
