import asyncio
import datetime

import storage
import aiosqlite
import pathlib
import logging
import typing
import contextlib

import trigger
import worker


class AioSqlitePool:
    def __init__(self, db_path: typing.Union[str, pathlib.Path],
                 pool_size: int):
        self._idle_queue: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue()
        self._busy_set: typing.Set[aiosqlite.Connection] = set()
        self._db_path = db_path
        self._pool_size = pool_size
        self._lock = asyncio.Lock()
        self._pool_size_limit = self._pool_size + 2
        self._py_logger: logging.Logger = logging.getLogger(f'cronweb.{self.__class__.__name__}')
        self._py_logger.debug('创建AioSqlitePool对象 初始连接池大小:%s 文件路径:%s', pool_size, db_path)

    @classmethod
    async def create_pool(cls, db_path: typing.Union[str, pathlib.Path],
                          pool_size: int = 2) -> "AioSqlitePool":
        inst = cls(db_path, pool_size)
        for i in range(pool_size):
            conn = await aiosqlite.connect(inst._db_path)
            await conn.execute("PRAGMA encoding='UTF-8';")
            await conn.commit()
            await inst._idle_queue.put(conn)
        return inst

    async def get_connection(self) -> aiosqlite.Connection:
        """返回数据库连接对象 超过30秒未返回则新建连接对象"""
        try:
            self._py_logger.debug('尝试从queue中获取连接对象')
            conn = await asyncio.wait_for(self._idle_queue.get(), timeout=30)
        except asyncio.TimeoutError as e:
            await self._lock.acquire()
            self._py_logger.error('数据库连接池获取超时 可能存在连接泄漏')
            if self._pool_size < self._pool_size_limit:
                self._py_logger.warning('尝试创建新数据库连接')
                conn = await aiosqlite.connect(self._db_path)
                await conn.execute("PRAGMA encoding='UTF-8';")
                await conn.commit()
                self._pool_size += 1
            else:
                self._lock.release()
                self._py_logger.error('数据库连接池超硬性限制')
                raise e
            self._lock.release()
        self._busy_set.add(conn)
        return conn

    async def back_connection(self, conn: aiosqlite.Connection):
        self._py_logger.debug('尝试归还数据库连接')
        self._busy_set.remove(conn)
        if not conn._running:
            self._py_logger.warning('数据库连接被意外关闭 尝试重新运行')
            conn.run()
        await self._idle_queue.put(conn)

    async def close(self):
        await self._lock.acquire()
        self._py_logger.debug('尝试关闭连接池 当前连接池大小:%s', self._pool_size)
        for i in range(self._pool_size):
            self._py_logger.debug('尝试关闭%s号连接', i)
            conn: aiosqlite.Connection = await self._idle_queue.get()
            await conn.close()
        self._lock.release()

    @contextlib.asynccontextmanager
    async def connect(self) -> aiosqlite.Connection:
        conn = await self.get_connection()
        try:
            yield conn
        finally:
            await self.back_connection(conn)


class AioSqliteStorage(storage.StorageBase):
    def __init__(self, db_pool: AioSqlitePool, db_path: typing.Union[str, pathlib.Path]):
        super().__init__()
        self.db_pool = db_pool
        self.db_path = db_path

    @classmethod
    async def create(cls, db_path: typing.Union[str, pathlib.Path]):
        pool = await AioSqlitePool.create_pool(db_path)
        self = cls(pool, db_path)
        await self.init_db()
        return self

    async def init_db(self):
        """设置编码为utf8 表不存在则建表"""
        async with self.db_pool.connect() as conn:

            sql = r"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            async with conn.execute(sql.format(table_name='jobs')) as cursor:
                if (await cursor.fetchone())[0] == 0:
                    self._py_logger.info('jobs表不存在 尝试创建')
                    await self._create_table_job()

            async with conn.execute(sql.format(table_name='job_logs')) as cursor:
                if (await cursor.fetchone())[0] == 0:
                    self._py_logger.info('job_logs表不存在 尝试创建')
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
        async with self.db_pool.connect() as conn:
            await conn.execute(sql)
            await conn.commit()

    async def _create_table_job_log(self):
        sql = """
            CREATE TABLE job_logs(
                shot_id NCHAR(32) PRIMARY KEY NOT NULL,
                uuid NCHAR(32) NOT NULL,
                state NCHAR(8) NOT NULL,
                log_path NVARCHAR NOT NULL,
                date_start TEXT NOT NULL,
                date_end TEXT DEFAULT NULL,
                deleted INTEGER DEFAULT 0
            );
        """
        async with self.db_pool.connect() as conn:
            await conn.execute(sql)
            await conn.commit()

    async def get_job(self, uuid: str) -> typing.Optional[trigger.JobInfo]:
        sql = r"""SELECT * FROM jobs WHERE uuid=? AND deleted=0"""
        async with self.db_pool.connect() as conn:
            async with conn.execute(sql, (uuid,)) as cursor:
                row = await cursor.fetchone()
                if len(row) == 0:
                    self._py_logger.warning('任务不存在于storage uuid:%s', uuid)
                    return None
                return trigger.JobInfo(row[0], row[1], row[2], row[3], row[4], row[5], row[6])

    async def get_all_jobs(self) -> typing.Dict[str, trigger.JobInfo]:
        sql = r"""SELECT * FROM jobs WHERE deleted=0"""
        async with self.db_pool.connect() as conn:
            async with conn.execute(sql) as cursor:
                rows = await cursor.fetchall()
                if len(rows) == 0:
                    self._py_logger.warning('storage中无任务')
                    return {}
                return {row[0]: trigger.JobInfo(row[0], row[1], row[2],
                                                row[3], row[4], row[5], row[6])
                        for row in rows}

    async def save_job(self, job_info: trigger.JobInfo) -> typing.Optional[trigger.JobInfo]:
        sql = r"""INSERT INTO jobs (uuid, cron_exp, command, param, name, date_create, date_update)
                    VALUES (?, ?, ?, ?, ?, ?, ?);"""
        self._py_logger.debug('尝试在storage中添加新任务 %s', job_info)
        async with self.db_pool.connect() as conn:
            try:
                await conn.execute(sql, tuple(job_info))
                await conn.commit()
            except Exception as e:
                self._py_logger.error('storage任务添加失败')
                self._py_logger.exception(e)
                raise e
        return job_info

    async def remove_job(self, uuid: str) -> typing.Optional[str]:
        """从数据库删除一个job"""
        sql = r"""DELETE FROM jobs WHERE uuid=?;"""
        self._py_logger.debug('尝试在storage中删除任务 %s', uuid)
        async with self.db_pool.connect() as conn:
            try:
                await conn.execute(sql, (uuid,))
                await conn.commit()
            except Exception as e:
                self._py_logger.error('storage任务删除失败')
                self._py_logger.exception(e)
                return None
        return uuid

    async def job_log_shoot(self, log_path: typing.Union[str, pathlib.Path],
                            shot_state: worker.JobState):
        sql = r"""INSERT INTO job_logs (shot_id, uuid, state, log_path, date_start)
                    VALUES (?, ?, ?, ?, ?);"""
        uuid = shot_state.uuid
        shot_id = shot_state.shot_id
        self._py_logger.debug('尝试在storage中添加新任务log记录 %s', uuid)
        async with self.db_pool.connect() as conn:
            try:
                log_path = pathlib.Path(log_path)
                date_start = datetime.datetime.fromtimestamp(float(log_path.stem.split('-')[0]) / 1000)
                await conn.execute(sql, (shot_id, uuid, shot_state.state.name,
                                         str(log_path), str(date_start)))
                await conn.commit()

            except Exception as e:
                self._py_logger.error('storage任务log添加失败')
                self._py_logger.exception(e)

    async def job_log_done(self, shot_state: worker.JobState):
        sql = r"""UPDATE job_logs SET state=?, date_end=? WHERE shot_id=?;"""
        self._py_logger.debug('尝试在storage中更新新任务log记录 shot_id:%s', shot_state.shot_id)
        now = datetime.datetime.now()
        async with self.db_pool.connect() as conn:
            try:
                await conn.execute(sql, (shot_state.state.name, str(now), shot_state.shot_id))
                await conn.commit()
            except Exception as e:
                self._py_logger.error('storage任务log更新失败')
                self._py_logger.exception(e)

    async def job_log_get_record(self, shot_id: str) -> typing.Optional[storage.LogRecord]:
        """通过shot_id获取日志文件的数据库记录"""
        # TODO 通过shot_id获取日志文件的数据库记录
        pass

    async def job_logs_get_by_uuid(self, uuid: str) -> typing.List[storage.LogRecord]:
        sql = r"""SELECT * FROM job_logs WHERE uuid=? AND deleted=0;"""
        self._py_logger.debug('尝试在storage中查询任务log记录 uuid:%s', uuid)
        async with self.db_pool.connect() as conn:
            async with conn.execute(sql, (uuid,)) as cursor:
                rows = await cursor.fetchall()
                out_list = [storage.LogRecord(row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows]
        return out_list

    async def job_logs_get_by_state(self, state: worker.JobStateEnum) -> typing.List[storage.LogRecord]:
        sql = r"""SELECT * FROM job_logs WHERE state=? AND deleted=0;"""
        self._py_logger.debug('尝试在storage中查询任务log记录 state:%s', state.name)
        async with self.db_pool.connect() as conn:
            async with conn.execute(sql, (state.name,)) as cursor:
                rows = await cursor.fetchall()
                out_list = [storage.LogRecord(row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows]
        return out_list

    async def job_logs_remove_shot_id(self, shot_id: typing.Union[str, typing.List[str]]) -> typing.List[str]:
        """根据shot_id从storage中删除记录"""
        # TODO 根据shot_id从storage中删除记录
        pass

    async def job_logs_set_deleted(self, uuid: str) -> typing.List[str]:
        """删除job时 将对应uuid的job log设置为deleted(并非真实删除)"""
        # TODO 删除job时 将对应uuid的job log设置为deleted
        pass

    async def job_logs_get_deleted(self) -> typing.List[storage.LogRecord]:
        """获取所有设置为deleted的shot_id 用于进一步清理"""
        # TODO 获取所有设置为deleted的shot_id 用于进一步清理
        pass

    async def stop(self):
        self._py_logger.info('尝试关闭storage连接池')
        await self.db_pool.close()
