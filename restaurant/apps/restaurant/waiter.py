from collections import deque

class Waiter:
    def __init__(self, restaurant):
        self.restaurant = restaurant
        self.log = self.restaurant.log
        self.orders_placed = {}
        self.busy = False
    
    def __repr__(self):
        return f"## waiter ##  restaurant_id {self.restaurant.id} - busy: {self.busy}"
    def __str__(self):
        return repr(self)

    @classmethod
    async def create(cls, restaurant):
        return cls(restaurant)
    async def order_food(self, customer_id, table_id, order_id):
        """
        send order to be prepared
        """
        await self.restaurant.work_for_cooks.put(
            {
                "name": "order_food",
                "payload": {
                    "customer_id": customer_id,
                    "table_id": table_id,
                    "order_id": order_id
                }
            }
        )
    async def take_order(self, customer_id, table_id, order_id):
        await self.restaurant.events_for_client.put(
            {
                "name": "take_order",
                "payload": {
                    "customer_id": customer_id,
                    "table_id": table_id,
                    "order_id": order_id
                }
            }
        )
    async def bring_bill(self, customer_id, table_id):
        await self.restaurant.events_for_client.put(
            {
                "name": "bring_bill",
                "payload": {
                    "customer_id": customer_id,
                    "table_id": table_id
                }
            }
        )
    async def start_service(self):
        try:
            while True:
                work = await self.restaurant.work_for_waiters.get()
                if work['event'] == 'game_over':
                    break
                
                self.log.warning(f"{self} # - work: {work}")

                # take order - dessert only
                if work['event'] == 'take_order':
                    await self.take_order(
                        work['customer'], 
                        work['table_id'],
                        work['order_id']
                    )

                if work['event'] == 'waiting_for_order':
                    # send order to cooks
                    await self.order_food(
                        work['customer'],
                        work['table_id'],
                        work['order_id']
                    )
                    
                # waiting_for_bill
                if work['event'] == 'waiting_for_bill':
                    ready_for_bill = True
                    customers = await self.restaurant.tables[work['table_id']].get_customers_at_table(sitting=True)

                    for customer in customers:
                        if customer['state'] in {2, 3, 1}:
                            self.log.warning(f"{self} cannot order bill yet - {customer['id']} is still eating or waiting for food")
                            ready_for_bill = False
                            break
                    if not ready_for_bill:
                        # check again later
                        continue

                    for customer in customers:
                        await self.bring_bill(customer['id'], work['table_id'])

        except Exception as e:
            self.log.exception(f"{self} - exiting - work: {work}")