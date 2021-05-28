import storage
import aiosqlite
import pathlib
import logging
import typing

import trigger
import worker


class AioSqliteStorage(storage.StorageBase):
    def __init__(self, db_conn: aiosqlite.Connection):
        super().__init__()
        self.db_conn = db_conn

    @classmethod
    async def create(cls, db_path: typing.Union[str, pathlib.Path]):
        db_conn = await aiosqlite.connect(db_path)
        self = cls(db_conn)
        await self.init_db()
        return self

    async def init_db(self):
        await self.db_conn.execute("PRAGMA encoding='UTF-8';")
        await self.db_conn.commit()

        sql = r"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        async with self.db_conn.execute(sql.format(table_name='jobs')) as cursor:
            if (await cursor.fetchone())[0] == 0:
                await self._create_table_job()

        async with self.db_conn.execute(sql.format(table_name='job_logs')) as cursor:
            if (await cursor.fetchone())[0] == 0:
                await self._create_table_job_log()

    async def _create_table_job(self):
        sql = """
            CREATE TABLE jobs(
                uuid NCHAR(32) PRIMARY KEY NOT NULL,
                cron_exp VARCHAR NOT NULL,
                command NVARCHAR NOT NULL,
                param NVARCHAR NOT NULL,
                name NVARCHAR NOT NULL,
                date_create TEXT NOT NULL,
                date_update TEXT NOT NULL,
                deleted INTEGER DEFAULT 0
            );
        """
        await self.db_conn.execute(sql)
        await self.db_conn.commit()

    async def _create_table_job_log(self):
        sql = """
            CREATE TABLE job_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid NCHAR(32) NOT NULL,
                state NCHAR(8) NOT NULL,
                log_path NVARCHAR NOT NULL,
                date_start TEXT NOT NULL,
                date_end TEXT DEFAULT NULL,
                deleted INTEGER DEFAULT 0
            );
        """
        await self.db_conn.execute(sql)
        print('create2')
        await self.db_conn.commit()

    async def get_job(self, uuid: str) -> trigger.JobInfo:
        # TODO
        pass

    async def get_all_jobs(self) -> typing.Dict[str, trigger.JobInfo]:
        # TODO
        pass

    async def save_job(self, job_info: trigger.JobInfo):
        # TODO
        pass

    async def job_log_shoot(self, uuid: str, log_path: typing.Union[str, pathlib.Path]):
        # TODO
        pass

    async def job_log_done(self, uuid: str, job_state: worker.JobState):
        # TODO
        pass

    async def job_log_get_by_id(self, uuid: str) -> typing.Optional[worker.JobState]:
        # TODO
        pass

    async def job_log_get_by_state(self, state: worker.JobStateEnum) -> typing.Set[str]:
        # TODO
        pass

    async def stop(self):
        await self.db_conn.close()
