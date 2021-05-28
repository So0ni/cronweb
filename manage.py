import asyncio
import cronweb


def init() -> cronweb.CronWeb:
    import logger.logger_aio
    import storage
    import trigger.trigger_aiocron
    import web.web_fastapi
    import worker.worker_aiosubprocess
    core = cronweb.CronWeb()
    logger_core = logger.logger_aio.AioLogger('./logs')
    trigger_core = trigger.trigger_aiocron.TriggerAioCron(core)
    web_core = web.web_fastapi.WebFastAPI(core)
    worker_core = worker.worker_aiosubprocess.AioSubprocessWorker(core)
    core.set_web_default(web_core).set_worker_default(worker_core). \
        set_trigger_default(trigger_core).set_log_default(logger_core)
    return core


async def main():
    core = init()
    await core.run()


if __name__ == '__main__':
    asyncio.run(main())
