import asyncio
from asyncio import Queue
from collections import deque, Counter
from concurrent.futures._base import CancelledError

from apps.restaurant.kitchen import Kitchen
from apps.restaurant.line import Line
from apps.restaurant.table import Table
from apps.restaurant.hostess import Hostess
from apps.restaurant.waiter import Waiter


class Restaurant:
    def __init__(
        self,
        server,
        connection_id,
        restaurant_id: str,
        table_count: int,
        dinner_prepare_time: int,
        dessert_prepare_time: int,
        line_number: int
    ):
        self.connection_id = connection_id
        self.id = restaurant_id
        self.server = server

        self.log = server.log

        self.db = server.data['restaurant']
        self.db_restaurants = self.db.tables['restaurants']

        ## Queues
        server.events_for_client[restaurant_id] = Queue()
        server.work_for_waiters[restaurant_id] = Queue()
        server.work_for_hostess[restaurant_id] = Queue()
        server.work_for_cooks[restaurant_id] = Queue()

        self.events_for_client = server.events_for_client[restaurant_id]
        self.work_for_waiters = server.work_for_waiters[restaurant_id]
        self.work_for_hostess = server.work_for_hostess[restaurant_id] 
        self.work_for_cooks = server.work_for_cooks[restaurant_id]
        ##

        # Kitchen
        self.dinner_prepare_time = dinner_prepare_time
        self.dessert_prepare_time = dessert_prepare_time

        self.db_tables = server.data['restaurant'].tables['tables']
        # Tables
        self.table_count = table_count

        # Line 
        self.line_number = line_number

        self.tasks = []
    @classmethod
    async def create(cls,
        server,
        connection_id,
        restaurant_id: str,
        table_count: int,
        dinner_prepare_time: int,
        dessert_prepare_time: int,
        line_number: int, 
    ):
        """
            "id": "restaurant_id",
            "state": 0,
            "tables": 4,
            "dinner_prepare_time": 10,
            "dessert_prepare_time": 2,
            "line_number": 10
        """
        await server.data['restaurant'].tables['restaurants'].insert(
            id=restaurant_id,
            state=0,
            tables=table_count,
            dinner_prepare_time=dinner_prepare_time,
            dessert_prepare_time=dessert_prepare_time,
            line_number=line_number
        )
        restaurant =  cls(
            server, connection_id, restaurant_id,
            table_count, dinner_prepare_time, 
            dessert_prepare_time, line_number
            )
    
        await restaurant._setup()
        return restaurant   

    async def _setup(self):
        # Tables
        self.tables = {i: await Table.create(self, i) for i in range(self.table_count)}

        self.kitchen = Kitchen(self)

        # Line
        self.line = await Line.create(self)

        # Hosteess
        self.hostess = await Hostess.create(self)

        # Waiter
        self.waiter = await Waiter.create(self)
    async def cleanup(self):

        # will exit waiters
        await self.work_for_waiters.put({'event': 'game_over'})

        # will exit hostess 
        await self.work_for_hostess.put({'event': 'game_over'})

        # will exit kitchen
        await self.work_for_cooks.put({'event': 'game_over'})

        await asyncio.sleep(8)

        for task in self.tasks:
            try:
                task.cancel()
            except CancelledError:
                continue

        await self.db_restaurants.delete(where={'id': self.id})


    async def get_available_tables(self):
        """
        returns table count of available=True tables
        and tables with less than 4 assigned customers
        """
        all_tables = await self.db_tables.select(
            'id', 'table_id', 'available',
            where={
                'restaurant_id': self.id,
                'available': True,
            }
        )
        available_tables = {}
        for table in all_tables:
            table_count = await self.get_customer_count_at_table(table['table_id'])
            if table_count['total'] == 4:
                # should be marked un-avaialable by waiter soon
                continue
            available_tables[table['table_id']] = table_count
        return available_tables
        
    async def get_customer_count_at_table(self, table_id, sitting=False):
        """
        returns count of customers assigned to table
        sitting=True
        returns count of customers sitting at table
        """
        return await self.tables[table_id].get_customer_count_at_table()


    async def restaurant_manager(self):
        """
        responsible for communictation to ws_client by watching queue 
        used by waiters & hostess
        config:
            "id": "restaurant_id",
            "state": 0,
            "tables": 4,
            "dinner_prepare_time": 10,
            "dessert_prepare_time": 2,
            "line_number": 10
        """
        self.log.warning(f"{self} starting restaurant_manager")
        loop = asyncio.get_event_loop()

        for table in self.tables:
            self.tasks.append(
                loop.create_task(
                    self.tables[table].start_service()
                )
            )
        for worker in [self.kitchen, self.line, self.hostess, self.waiter]:
            self.tasks.append(
                loop.create_task(
                    worker.start_service()
                )
            )

        try:
            while True:
                event = await self.events_for_client.get()
                self.log.warning(f"## restaurant_manager running ## event for client: {event}")
                if 'event' in event and event['event'] == 'game_over':
                    break
                await self.server.connection_manager.send_json(self.connection_id, event)
        except Exception as e:
            self.log.exception(f"## restaurant_manager exiting ## error processing event for client: {event}")
        finally:
            await self.cleanup()