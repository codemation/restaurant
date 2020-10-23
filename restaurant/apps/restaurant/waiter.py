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

                # table full
                if work['event'] == 'ready_for_order':
                    #customers = await self.restaurant.tables[work['table_id']].get_customers_at_table(sitting=True)

                    meal_check = [work['customers'][c]['meal_choice'] for c in work['customers']]
                    options = []
                    if 'both' in meal_check:
                        options = ['dinner', 'both']
                    elif 'dinner' in meal_check:
                        options = ['dinner']
                    else:
                        options = ['dessert']
                    #order = 'dinner' if True in dinner_check else 'dessert'
                    
                    for customer in work['customers']:
                        meal_choice = work['customers'][customer]['meal_choice']
                        if not meal_choice in options:
                            continue

                        order_id = 0 if 'dinner' in options else 1
                        await self.take_order(
                            customer, 
                            work['table_id'],
                            order_id
                        )
                    continue
                if work['event'] == 'waiting_for_order':
                    # send order to cooks
                    await self.order_food(
                        work['customer'],
                        work['table_id'],
                        work['order_id']
                    )

                # ready_for_dessert
                if work['event'] == 'ready_for_dessert':
                    ready_for_dessert = True
                    customers = await self.restaurant.tables[work['table_id']].get_customers_at_table(sitting=True)

                    for customer in customers:
                        if customer['state'] == 3:
                            self.log.warning(f"{self} cannot order dessert yet - {customer['id']} is still eating")
                            ready_for_dessert = False
                            break
                    if not ready_for_dessert:
                        # check again later
                        await self.restaurant.work_for_waiters.put(work)
                        continue
                        
                    # add work to cooks queue
                    for customer in customers:
                        if not customer['will_have_dessert']:
                            continue
                        await self.order_food(
                            customer['id'],
                            work['table_id'],
                            1
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

                # handle stressed customers
                if work['event'] in {'stress_raised','high_stress_customer'}:
                    customer = work['customer']

                    if busy or customer['stress_level'] < 50:
                        continue
                    
                    # mark table un-available if not already - ensure ordering starts ASAP
                    await self.restaurant.tables['table_id'].set_is_table_available(False)

        except Exception as e:
            self.log.exception(f"{self} - exiting - work: {work}")