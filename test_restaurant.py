from unittest import TestCase
import asyncio
from aiohttp import ClientSession, WSMsgType
import uuid, random, logging, time



class Client:
    def __init__(self):
        self.host = '0.0.0.0'
        self.port = 8390
        self.game_path = '/testing'

        #connection 
        self.session_id = str(uuid.uuid1())
        self.sessions = {}
        self.client_connections = {}
        self.receive_locked = False
        self.setup_logger()
        # incoming
        self.events = asyncio.Queue()

        # outgoing
        self.events_for_server = asyncio.Queue()

        self.dinner_prep_time = 10
        self.dessert_prep_time = 2
        self.customers = {}
        self.tables = {}
    async def customers_eating_at_table(self, table_id):
        for customer in self.tables[table_id]:
            if self.customers[customer]['state'] == 3:
                return True
    async def game_over(self):
        await self.events_for_server.put(
            {
                "name": "restaurant_update",
                "payload": {
                        "id": self.session_id,
                        "state": 1
                }
            }
        )

    def setup_logger(self, logger=None, level=None):
        if logger == None:
            level = logging.DEBUG if level == 'DEBUG' else logging.ERROR
            logging.basicConfig(
                level=level,
                format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                datefmt='%m-%d %H:%M'
            )
            self.log = logging.getLogger(f'wsRpc-proxy')
            self.log.propogate = False
            self.log.setLevel(level)

    async def get_endpoint_sessions(self, endpoint):
        """
        pulls endpoint session if exists else creates & returns
        """
        loop = asyncio.get_running_loop()
        async def session():
            async with ClientSession(loop=loop) as client:
                #trace(f"started session for endpoint {endpoint}")
                while True:
                    status = yield client
                    if status == 'finished':
                        #trace(f"finished session for endpoint {endpoint}")
                        break
        if not endpoint in self.sessions:
            self.sessions[endpoint] = [{'session': session(), 'loop': loop}]
            return await self.sessions[endpoint][0]['session'].asend(None)
        for client in self.sessions[endpoint]:
            if loop == client['loop']:
                return await client['session'].asend(endpoint)

        #log.warning("session existed but not for this event loop, creating")
        client = session()
        self.sessions[endpoint].append({'session': client, 'loop': loop})
        return await client.asend(None)
    async def process_received_events(self):
        try:
            while True:
                print(f"## process_received_events ##: events: {self.events}" )
                event = await self.events.get()
                print(event)
                name = event['name']
                data = event['payload']
                customer_id = data['customer_id']
                if customer_id in self.customers:
                    if name == 'please_leave':
                        if not self.customers[customer_id]['state'] == 0:
                            continue
                        will_eat_anything = (
                            self.customers[customer_id]['will_have_dinner']
                            or self.customers[customer_id]['will_have_dessert']
                        )
                        satisfied = True if not will_eat_anything else False
                        stress_level = self.customers[customer_id]['stress_level'] if satisfied else 100
                        await self.events_for_server.put({
                                "name": "customer_update",
                                "payload": {
                                        "id": customer_id,
                                        "state": 5,
                                        "stress_level": stress_level,
                                        "satisfied": satisfied
                                }
                            }
                        )
                    if name == 'please_sit':
                        self.customers[customer_id]['table'] = data['table_id']
                        if not data['table_id'] in self.tables:
                            self.tables[data['table_id']] = []
                        self.tables[data['table_id']].append(customer_id)

                        line_time = time.time() - self.customers[customer_id]['line_time']
                        stress_range = (0, 5) if line_time < self.dinner_prep_time else (5, 10)
                        self.customers[customer_id]['stress_level'] += random.randint(*stress_range)
                        await self.events_for_server.put({
                            "name": "customer_update",
                            "payload": {
                                'id': customer_id,
                                'stress_level': self.customers[customer_id]['stress_level'],
                                'state': 1
                            }
                        }
                        )
                        self.customers[customer_id]['waiting_to_order'] = time.time()
                    if name == 'take_order':
                        """
                        {
                            "name": "take_order",
                            "payload": {
                                    "customer_id": customer_id,
                                    "table_id": 4,
                                    "order_id": 0
                            }
                        }
                        """
                        order_id = data['order_id']
                        table_id = data['table_id']

                        # dessert check
                        if order_id == 1:
                            # check that no one is eating at table
                            if await self.customers_eating_at_table(table_id):
                                await self.game_over()

                        waiting_to_order = time.time() - self.customers[customer_id]['waiting_to_order']
                        stress_range = (0, 5) if waiting_to_order < self.dinner_prep_time else (5, 10)
                        self.customers[customer_id]['stress_level'] += random.randint(*stress_range)         
                        await self.events_for_server.put({
                            "name": "customer_update",
                            "payload": {
                                'id': customer_id,
                                'stress_level': self.customers[customer_id]['stress_level'],
                                'state': 2
                            }
                        })
                        self.customers[customer_id]['waiting_on_food'] = time.time()
                    if name == 'deliver_order':
                        """
                        {
                            "name": "deliver_order",
                            "payload": {
                                    "id": "someid",
                                    "table_id": 4,
                                    "order_id": 0
                            }
                        }
                        """
                        order_id = data['order_id']
                        table_id = data['table_id']
                        if order_id == 0:
                            prep_time = self.dinner_prep_time
                        else:
                            prep_time = self.dessert_prep_time
                        if time.time() - self.customers[customer_id]['waiting_on_food'] < prep_time:
                            await self.game_over()

                        delivery_time = time.time() - self.customers[customer_id]['waiting_on_food']
                        stress_range = (0, 5) if delivery_time < prep_time + 5  else (5, 10)
                        self.customers[customer_id]['stress_level'] += random.randint(*stress_range)

                        await self.events_for_server.put({
                            "name": "customer_update",
                            "payload": {
                                'id': customer_id,
                                'stress_level': self.customers[customer_id]['stress_level'],
                                'state': 3
                            }
                        })
                        async def eat_time(customer_id, dessert=False):
                            try:
                                meal = 'dinner' if not dessert else 'dessert'
                                self.log.warning(f"{customer_id} started eating {meal}")
                                await asyncio.sleep(random.randint(2,5))
                                if dessert:
                                    # waiting for order
                                    await self.events_for_server.put({
                                        "name": "customer_update",
                                        "payload": {
                                            'id': customer_id,
                                            'stress_level': self.customers[customer_id]['stress_level'],
                                            'state': 2
                                        }
                                    })
                                else:
                                    # waiting bill
                                    await self.events_for_server.put({
                                        "name": "customer_update",
                                        "payload": {
                                            'id': customer_id,
                                            'stress_level': self.customers[customer_id]['stress_level'],
                                            'state': 4
                                        }
                                    })
                                    self.customers[customer_id]['waiting_on_bill'] = time.time()
                                self.log.warning(f"{customer_id} finished eating {meal}")
                            except Exception as e:
                                self.log.exception(f"error during eat_time")

                        if order_id == 0 and self.customers[customer_id]['will_have_dessert']:
                            asyncio.create_task(eat_time(customer_id, dessert=True))
                        else:
                            asyncio.create_task(eat_time(customer_id))

                    if name == 'bring_bill':
                        """
                        {
                            "name": "bring_bill",
                            "payload": {
                                    "customer_id": "someid",
                                    "table_id": 4
                            }
                        }
                        """
                        table_id = data['table_id']
                        # game over if bring_bill while eating
                        if await self.customers_eating_at_table(table_id):
                            await self.game_over()
                        time_waiting_on_bill = time.time() - self.customers[customer_id]['waiting_on_bill']
                        stress_range = (0, 5) if time_waiting_on_bill > 5 else (5, 10)
                        self.customers[customer_id]['stress_level'] += random.randint(*stress_range)
                        stress_level = self.customers[customer_id]['stress_level']
                        satisfied = True if stress_level < 100 else False
                        await self.events_for_server.put({
                            "name": "customer_update",
                            "payload": {
                                'id': customer_id,
                                'stress_level': self.customers[customer_id]['stress_level'],
                                'state': 5,
                                'satisfied': satisfied
                            }
                        })
        except Exception as e:
            self.log.exception(f"error in process_received_events")
    async def get_client_ws_session(self):
        """
        pulls endpoint session if exists else creates & returns
        """
        async def ws_client():
            session = await self.get_endpoint_sessions(self.session_id)
            url = f"http://{self.host}:{self.port}{self.game_path}"
            async with session.ws_connect(
                url #timeout=600, heartbeat=120.0
                ) as ws:
                async def process_received():
                    try:
                        while True:
                            result = await ws.receive()
                            #print(result.type)
                            print(f"process_received {result}")
                            result = result.json()
                            if 'name' in result:
                                await self.events.put(result)
                                print(self.events)
                            await asyncio.sleep(0.05)
                    except Exception as e:
                        self.log.exception(f"client receiver exiting")
                async def process_events_to_server():
                    try:
                        while True:
                            event = await self.events_for_server.get()
                            print(f"## process_events_to_server ### sending {event} to game_server")
                            await ws.send_json(event)
                    except Exception as e:
                        self.log.exception(f"process_events_to_server exiting")
                        
                async def keep_alive():
                    last_ping = time.time()
                    try:
                        while True:
                            if time.time() - last_ping > 10:
                                await self.events_for_server.put({'ping': 'ping'})
                                #result = await ws.send_json({'ping': 'ping'})
                                #self.log.warning(f"ping send: {result}")
                                #while self.receive_locked:
                                #    await asyncio.sleep(0.01)
                                try:
                                    self.receive_locked = True
                                    #result = await ws.receive()
                                    #self.log.warning(f"ping result: {result}")
                                    self.receive_locked = False
                                except Exception as e:
                                    self.receive_locked = False
                                    raise e
                                #self.log.warning(f" keep alive receive {result}")
                                last_ping = time.time()
                            await asyncio.sleep(3)
                    except Exception as e:
                        self.log.exception(f"keep alive exiting")
                loop = asyncio.get_event_loop()
                loop.create_task(process_events_to_server())
                loop.create_task(keep_alive())
                loop.create_task(process_received())
                loop.create_task(self.process_received_events())
                while True:
                    status = yield ws
                    if status == 'finished':
                        self.log.debug(f"########### status is {status} #######")
                        break
            return
        if self.session_id and not self.session_id in self.client_connections:
            self.client_connections[self.session_id] = ws_client()
            return await self.client_connections[self.session_id].asend(None)
        return await self.client_connections[self.session_id].asend(None)

    async def cleanup_client_session(self):
        try:
            await self.client_connections[self.session_id].asend('finished')
        except StopAsyncIteration:
            pass
        del self.client_connections[self.session_id]

    async def make_client_request(self, request: dict, get_result=False):
        for _ in range(2):
            try:
                #while self.receive_locked:
                #    await asyncio.sleep(0.01)
                self.receive_locked = True
                ws = await self.get_client_ws_session()
                #await ws.send_json(request)
                await self.events_for_server.put(request)
                try:
                    if get_result:
                        result = await self.events.get()
                        self.log.warning(f"make_client_request result: {result}")
                        if 'error' in result:
                            raise Exception(result['error'])
                except Exception as e:
                    self.receive_locked = False
                    raise e
                self.receive_locked = False
                if get_result:
                    return result
                return
            except Exception as e:
                last_exception = e
                self.log.exception(f"error during make_proxy_request")
                await self.cleanup_client_session()
                continue
        raise last_exception

async def new_customer(client, restaurant_id):
    new_customer_id = str(uuid.uuid1())
    client.customers[new_customer_id] = {
                    "id": new_customer_id,
                    "restaurant_id": restaurant_id,
                    "state": 0,
                    "stress_level": random.randint(1, 20),
                    "sit_together": [],
                    "will_have_dinner": random.choice([True, False]),
                    "will_have_dessert": random.choice([True, False])
    }
    result = await client.make_client_request(
        {
            "name": "customer_update",
            "payload": client.customers[new_customer_id]
        }
    )
    client.customers[new_customer_id]['line_time'] = time.time()

async def test_main():
    c = Client()
    restaurant_id = str(uuid.uuid1())
    await c.make_client_request(
        {
            "name": "restaurant_update",
            "payload": {
                    "id": c.session_id,
                    "state": 0,
                    "tables": 8,
                    "dinner_prepare_time": c.dinner_prep_time,
                    "dessert_prepare_time": c.dessert_prep_time,
                    "line_number": 20
            }
        }
    )
    await new_customer(c, c.session_id)
    await new_customer(c, c.session_id)
    await new_customer(c, c.session_id)
    while True:
        try:
            await new_customer(c, c.session_id)
            await asyncio.sleep(0.5)
        except Exception as e:
            c.log.exception("error in creating new customers")
            print(repr(e))
            break

if __name__ == '__main__':
    asyncio.run(test_main(), debug=True)

class TestRestaurant(TestCase):
    def test__game(self):
        #loop = asyncio.get_event_loop()
        #loop.set_debug(enabled=True)
        #asyncio.run()
        asyncio.run(test_main(), debug=True)