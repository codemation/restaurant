import asyncio
class Line:
    def __init__(self, restaurant):
        self.restaurant = restaurant
        self.log = self.restaurant.log

        self.line_number = self.restaurant.line_number
        self.customers_in_line = set()
        self.last_len = 0
        self.line_status = None
        
        self.db_customers = self.restaurant.server.data['restaurant'].tables['customers']
    def __repr__(self):
        return f"## line ##  restaurant_id {self.restaurant.id} {len(self.customers_in_line)}/{self.line_number} - status: {self.line_status}"
    def __str__(self):
        return repr(self)
    @classmethod
    async def create(cls, restaurant):
        return cls(restaurant)

    async def get_customers_in_line(self):
        customers_in_line = await self.db_customers.select(
            '*', 
            where = {
                'state': 0,
                'restaurant_id': self.restaurant.id
            }
        )
        return customers_in_line
    async def update_hostess(self, event):
        await self.restaurant.work_for_hostess.put(event)
    
    async def start_service(self):
        try:
            while True:
                """
                monitor queue capacity and submit work to hostess queues
                """
                await asyncio.sleep(3)

                self.log.warning(f"{self} running - customers: {self.customers_in_line} - hostess work: {self.restaurant.work_for_hostess}")

                # get all customers in line
                customers_in_line = await self.get_customers_in_line()

                for customer in customers_in_line:
                    if not customer['id'] in self.customers_in_line:
                        await self.restaurant.work_for_hostess.put(
                            {
                                'event': 'request_table',
                                'customer': customer
                            }
                        )
                self.customers_in_line = {c['id'] for c in customers_in_line}
                current_line_count = len(customers_in_line)

                if self.last_len == 0: 
                    if current_line_count == 0:
                        # line is empty - no changes
                        continue
                if current_line_count == 0 and not self.line_status == 'line_is_empty':
                    self.line_status = 'line_is_empty'
                    await self.update_hostess({'event': 'line_is_empty'})

                if ( current_line_count / self.line_number >= 3/4 and  
                    not self.line_status == 'line_near_capacity'):
                    self.line_status = 'line_near_capacity'
                    await self.update_hostess({'event': 'line_near_capacity'})
                    continue
                # 2/4 capacity
                if (current_line_count / self.line_number >= 2/4 and 
                    not self.line_status == 'line_half_capacity'):
                    self.line_status = 'line_half_capacity'
                    await self.update_hostess({'event': 'line_half_capacity'})
                    continue
                # 1/4 capacity
                if (current_line_count / self.line_number >= 1/4 and  
                    not self.line_status == 'line_partial_capacity'):
                    self.line_status = 'line_partial_capacity'
                    await self.update_hostess({'event': 'line_partial_capacity'})
                    continue
        except Exception as e:
            self.log.exception(f"{self} exiting - customers: {self.customers_in_line}")