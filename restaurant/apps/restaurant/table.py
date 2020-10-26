import asyncio
from collections import Counter

class Table:
    def __init__(self, restaurant, table_number: str):
        self.restaurant = restaurant
        self.id = f"{restaurant.id}_{table_number}"
        self.table_number = table_number
        self.db_table = self.restaurant.server.data['restaurant'].tables['tables']
        self.log = self.restaurant.log
        self.reset_service()    
    @classmethod
    async def create(cls, restaurant, table_number: str):
        tables = restaurant.server.data['restaurant'].tables['tables']
        
        await tables.insert(
            id=f"{restaurant.id}_{table_number}",
            table_id=table_number,
            restaurant_id=restaurant.id,
            available=True
        )
        return cls(restaurant, table_number)
    def __repr__(self):
        return f"## table ## avail: {self.available} customers: {len(self.customers)} - meal_order: {self.meal_order} - {self.meal_customer_order} - state: {[self.customers[c]['state'] for c in self.customers]} - eating: {self.eating}" 
    def __str__(self):
        return repr(self)
    async def update(self, values_to_update: dict):
        await self.db_table.update(
            **values_to_update,
            where={'id': self.id}
        )
    async def get(self, values_to_get: list):
        return await self.db_table.select(
            *values_to_get,
            where={'id': self.id}
        )
    def reset_service(self):
        self.available = True
        self.eating = {}
        self.meal_customer_order = {}

        self.meal_started = False
        self.meal_order = []
        self.customers = {}

        self.requested_bill = False

        self.log.warning(f"{self} - service is reset")
    async def set_is_table_available(self, is_available: bool):
        await self.update({'available': is_available})
        self.available = is_available
    async def get_is_table_available(self):
        result =  await self.get(['available'])
        return result[0]['available']
    async def get_customer_count_at_table(self, sitting=False):
        """
        returns count of customers assigned to table
        sitting=True
        returns count of customers sitting at table
        """
        customers = await self.get_customers_at_table(sitting=sitting)
        count = {'dinner': 0, 'dessert': 0, 'both': 0, 'total': len(customers)}
        for customer in customers:
            if customer['will_have_dinner'] and customer['will_have_dessert']:
                count['both'] +=1
            elif customer['will_have_dinner']:
                count['dinner'] +=1
            else:
                count['dessert'] +=1
        return count
    async def get_customers_at_table(self, sitting=False):
        """
        default:
            returns customers assigned to table
        sitting=True
            returns customers sitting at table ( checks state)
        """
        customers = self.restaurant.server.data['restaurant'].tables['customers']
        if sitting:
            where=[
                {'table_id': self.table_number},
                {'restaurant_id': self.restaurant.id},
                ['state', '<>', 0]
            ]
        else:
            where={
                'table_id': self.table_number,
                'restaurant_id': self.restaurant.id
            }

        customers_at_table = await customers.select(
            '*',
            where=where
        )
        return customers_at_table
    async def remove_customer_from_table(self, customer_id):
        customers = self.restaurant.server.data['restaurant'].tables['customers']
        await customers.delete(
            where={'id': customer_id}
        )

    async def request_bill(self):
        if not self.requested_bill:
            await self.restaurant.work_for_waiters.put(
                {
                    'event': 'waiting_for_bill',
                    'table_id': self.table_number,
                    'customer': self.customers
                }
            )
            self.requested_bill = True
    async def define_meal_order(self):
        meal_order = []
        dinner = []
        dessert = []

        customers_at_table = await self.get_customers_at_table(sitting=True)
        for customer in customers_at_table:
            if customer['will_have_dinner'] and customer['will_have_dessert']:
                dinner.append(customer['id'])
                dessert.append(customer['id'])
                meal_order = [0,1]
            elif customer['will_have_dinner']:
                dinner.append(customer['id'])
                if not 0 in meal_order:
                    meal_order.append(0)
            else:
                dessert.append(customer['id'])
                if not 1 in meal_order:
                    meal_order.append(1)
        if len(dinner) > 0:
            self.meal_customer_order[0] = set(dinner)
        if len(dessert) > 0:
            self.meal_customer_order[1] = set(dessert)
        self.meal_order = [0,1] if len(meal_order) > 1 else meal_order
        self.meal_started = True
    async def notify_eating(self, customer_id, eating: bool, order: int = None):
        if eating and not customer_id in self.eating:
            self.eating[customer_id] = order
        if not eating and customer_id in self.eating:
            #order = 
            del self.eating[customer_id]
            self.meal_customer_order[self.meal_order[0]].discard(customer_id)
            #if customer_id in self.eating:
            
            if len(self.eating) == 0 and len(self.meal_customer_order[self.meal_order[0]]) == 0:
                del self.meal_order[0]
                if len(self.meal_order) > 0:
                    await self.notify_ready_to_order()
                else:
                    await self.request_bill()
        if len(self.eating) == 0 and len(self.meal_order) == 0:
            await self.request_bill()
        self.log.warning(f"{self} - notify_eating - {customer_id}")
                    
    async def notify_waiting_for_order(self, customer_id, order_id):
        await self.restaurant.work_for_waiters.put(
            {
                'event': 'waiting_for_order',
                'table_id': self.table_number,
                'customer': customer_id,
                'order_id': order_id
            }
        )
    async def notify_ready_to_order(self):
        if not self.meal_started:
            await self.define_meal_order()
        customers_at_table = await self.get_customers_at_table(sitting=True)
        order = self.meal_order[0]
        for customer in customers_at_table:
            if customer['id'] in self.meal_customer_order[order]:
                # dessert only - need to issue take_order
                if customer['state'] == 1:
                    await self.notify_take_order(customer['id'], self.meal_order[0])
                if customer['state'] == 2:
                    await self.notify_waiting_for_order(customer['id'], self.meal_order[0])


    async def notify_take_order(self, customer_id, order_id):
        await self.restaurant.work_for_waiters.put(
            {
                'event': 'take_order',
                'table_id': self.table_number,
                'customer': customer_id,
                'order_id': self.meal_order[0]
            }
        )        


    async def notify_start_order(self):
        await self.define_meal_order()
        customers_at_table = await self.get_customers_at_table(sitting=True)
        for customer in customers_at_table:
            if not customer['will_have_dinner'] and self.meal_order[0] == 0:
                continue
            if not customer['will_have_dessert'] and self.meal_order[0] == 1:
                continue
            await self.notify_take_order(customer['id'], self.meal_order[0])

    def update_customers(self, latest_customers):
        self.log.warning(f"{self} - update_customers")
        for customer in latest_customers:
            if customer['id'] in self.customers:
                self.customers[customer['id']].update(customer)
            else:
                self.customers[customer['id']] = customer
        if len(latest_customers) == 0:
            self.customers = {}
    async def update_customer(self, customer: dict):
        customer_id = customer['id']
        dinner = customer['will_have_dinner']
        dessert = customer['will_have_dessert']
        # customer just ordered
        if self.customers[customer_id]['state'] == 1 and customer['state'] == 2:
            await self.notify_waiting_for_order(
                customer_id,
                0 if dinner else 1
            )
        # customer just finished dinner and is ready for dessert
        if self.customers[customer_id]['state'] == 3 and customer['state'] == 2:
            await self.notify_eating(customer_id, False)

        # ready for the bill
        if self.customers[customer_id]['state'] == 3 and customer['state'] == 4:
            await self.notify_eating(customer_id, False)

        if customer['state'] == 2:
            await self.notify_eating(customer_id, False)
        if customer['state'] == 3:
            await self.notify_eating(customer_id, True, self.meal_order[0])
        
        if customer['state'] == 4:
            await self.notify_eating(customer_id, False)

        if customer['state'] == 5:
            await self.remove_customer_from_table(customer_id)


    async def start_service(self):
        try:
            while True:
                await asyncio.sleep(1)
                self.log.warning(f"{self}")
                available = await self.get_is_table_available()
                customers_at_table = await self.get_customers_at_table(sitting=True)
                if not available and len(customers_at_table) == 0:
                    self.reset_service()
                    await self.set_is_table_available(True)
                    continue
                if self.available and (not available or len(customers_at_table) == 4):
                    await self.set_is_table_available(False)
                    await self.notify_ready_to_order()
                start_meal_early = False
                for customer in customers_at_table:
                    if not customer['id'] in self.customers:
                        self.customers[customer['id']] = customer
                    if not self.meal_started and not self.restaurant.hostess.busy and customer['stress_level'] > 50:
                        start_meal_early = True

                    if not self.customers[customer['id']]['state'] == customer['state']:
                        await self.update_customer(customer)
                    if start_meal_early:
                        await self.set_is_table_available(False)
                        await self.notify_ready_to_order()

                self.update_customers(customers_at_table)
        except Exception as e:
            self.log.exception(f"{self} exiting")