import aiosqlite as asq

class Database:
    @staticmethod
    async def _connect():
        db=await asq.connect("database.db")
        cur= await db.cursor()
        return db,cur

    @staticmethod
    async def _fetchone(cursor:asq.Cursor):
        return await cursor.fetchone()
    
    @staticmethod
    async def _fetchall(cursor:asq.Cursor):
        return await cursor.fetchall()

    @staticmethod
    async def _commit(db:asq.Connection):
        cursor = await db.cursor()
        await db.commit()
        await cursor.close()
        await db.close()

    async def execute(self,query:str,*values:tuple):
        db,cursor = await self._connect()
        await cursor.execute(query,values)
        await self._commit(db)

    async def fetchone(self,query:str,*values:tuple):
        db,cursor = await self._connect()
        await cursor.execute(query,values)
        result = await self._fetchone(cursor)
        return result[0] if result is not None else None

    async def fetchall(self,query:str,*values:tuple):
        db,cursor = await self._connect()
        await cursor.execute(query,values)
        return await self._fetchall(cursor)