import asyncio
class Kitchen:
    def __init__(self, restaurant):
        self.restaurant = restaurant
        self.log = self.restaurant.log

        self.dinner_prepare_time = self.restaurant.dinner_prepare_time
        self.dessert_prepare_time = self.restaurant.dessert_prepare_time
    def __repr__(self):
        return f"## kitchen ##  restaurant_id {self.restaurant.id}"
    def __str__(self):
        return repr(self)
    async def cook_and_deliver(self, order):
        try:
            customer_id, table_id, order_id = order['customer_id'], order['table_id'], order['order_id']
            cook_time = self.dinner_prepare_time if order_id == 0 else self.dessert_prepare_time

            self.log.warning(f"{self} - starting cooking order {order}")
            await asyncio.sleep(cook_time)
            self.log.warning(f"{self} - finished cooking order {order}")
            await self.deliver_food(customer_id, table_id, order_id)
        except Exception as e:
            self.log.exception(f"{self} error cooking order {order}")
    async def deliver_food(self, customer_id, table_id, order_id):
        await self.restaurant.events_for_client.put(
            {
                "name": "deliver_order",
                "payload": {
                    "customer_id": customer_id,
                    "table_id": table_id,
                    "order_id": order_id
                }
            }
        )
        #del self.restaurant.tables[table_id].customer_waiting_on[customer_id]
    async def start_service(self):
        try:
            self.log.warning(f"{self} starting")
            while True:
                work = await self.restaurant.work_for_cooks.get()
                self.log.warning(f"{self} received order: {work}")
                self.restaurant.server.event_loop.create_task(
                    self.cook_and_deliver(work['payload'])
                )
        except Exception as e:
            self.log.exception(f"{self} exiting")