from collections import deque

class Hostess:
    def __init__(self, restaurant):
        self.restaurant = restaurant
        self.log = self.restaurant.log

        self.waiting_list = {
            'dinner': set(), 'dessert': set(), 
            'both': set(), 'none': set(),
            'customers': {}, 'queue': deque() 
            }
        self.tables = {}
        self.busy = False
        self.line_is_empty = True
        self.status = 'line_is_empty'

        self.db_customers = self.restaurant.db.tables['customers']

    def __repr__(self):
        return f"## hostess ##  restaurant_id {self.restaurant.id} - busy: {self.busy} - tables: {self.tables} - waiting_list: {self.waiting_list}" 
    def __str__(self):
        return repr(self)

    @classmethod
    async def create(cls, restaurant):
        return cls(restaurant)

    async def organize_tables(self):
        try:
            available_tables = await self.restaurant.get_available_tables()
            table_count = len(available_tables)
            label_tables = (t for t in available_tables)
            reserve_count = int(table_count * .25)
            for table_type in {'both', 'dinner', 'dessert', 'open'}:
                self.tables[table_type] = {}
                for _ in range(reserve_count):
                    t_id = next(label_tables)
                    self.tables[table_type][t_id] = 4
                    self.tables[t_id] = table_type
            for t_id in label_tables:
                self.tables['open'][t_id] = 4
                self.tables[t_id] = 'open'
        except Exception as e:
            self.log.exception(f"{self} error in organizing tables")
    async def assign_customer_table(self, customer_id, table_id):
        """
        used by hostess to direct customer to table
        """
        if customer_id in self.waiting_list['customers']:
            # update db
            await self.db_customers.update(
                table_id=table_id,
                where={
                    'id': customer_id
                }
            )

            # send please_sit 
            await self.restaurant.events_for_client.put(
                {
                    "name": "please_sit",
                    "payload": {
                        "customer_id": customer_id,
                        "table_id": table_id
                    }
                }
            )
    async def run_capcacity_control(self):
        """
        run to reduce capacity by 25 % so restaurant stays open
        """
        # remove all customers which will order nothing, and any sit_together customers

        # remove members from end of end of line( waiting the least amount of time ) 
        # 
        # - both + members
        # - dinner + members
        # - dessert + members
        # # Then Target Individuals
        try:
            capacity = self.restaurant.line.line_number
            number_to_remove = int(capacity * .25)
            self.log.warning(f"{self} capacity control started to remove {number_to_remove} customers")
            queue = self.waiting_list['queue'].copy()
            for _ in range(number_to_remove):
                if len(self.waiting_list['none']) > 0:
                    for customer in self.waiting_list['none']:
                        await self.remove_customer_from_line(customer)
                        number_to_remove-=1
                queue = self.waiting_list['queue'].copy()
                if number_to_remove == 0:
                    break
                try:
                    customer = queue.pop()
                    await self.remove_customer_from_line(customer)
                except IndexError:
                    break

            self.log.warning(f"{self} capacity control completed")
        except Exception as e:
            self.log.warning(f"{self} error during capacity control")

    async def remove_customer_from_line(self, customer):
        self.log.warning(f"{self} remove_customer_from_line - customer_id: {customer}")
        if customer in self.waiting_list['customers']:
            m_choice = self.waiting_list['customers'][customer]['meal_choice']
            self.waiting_list[m_choice].discard(customer)
            del self.waiting_list['customers'][customer]
        if customer in self.waiting_list['queue']:
            self.waiting_list['queue'].remove(customer)

        await self.restaurant.events_for_client.put(
            {
                "name": "please_leave",
                "payload": {
                    "customer_id": customer
                }
            }
        )

    async def start_service(self):
        try:
            await self.organize_tables()
            while True:
                work = await self.restaurant.work_for_hostess.get()
                self.log.warning(f"{self} - work {work}")
                if work['event'] == 'game_over':
                    break
                # events
                if self.tables:
                    available_tables = await self.restaurant.get_available_tables()
                    # update current availability count
                    for t_id in available_tables:
                        self.tables[self.tables[t_id]][t_id] = 4 - available_tables[t_id]['total']

                #request_table
                if work['event'] == 'request_table':
                    customer = work['customer']
                    meal_choice = 'none'
                    if customer['will_have_dinner'] and customer['will_have_dessert']:
                        meal_choice = 'both'
                    elif customer['will_have_dinner']:
                        meal_choice = 'dinner'
                    elif customer['will_have_dessert']:
                        meal_choice = 'dessert'
                    else:                    
                        pass
                    self.waiting_list[meal_choice].add(customer['id'])
                    self.waiting_list['customers'][customer['id']] = {
                        'sit_together': customer['sit_together']['sit_together'],
                        'meal_choice': meal_choice
                        }
                    self.waiting_list['queue'].append(customer['id'])

                self.log.warning(f"{self} - {work}")

                # line_near_capacity
                if work['event'] == 'line_near_capacity':
                    self.busy = True
                    self.restaurant.waiter.busy = True

                    # trigger line control logic
                    if not self.status == 'line_near_capacity':
                        await self.run_capcacity_control()

                # line_half_capacity
                if work['event'] == 'line_half_capacity':
                    self.busy = True
                    self.restaurant.waiter.busy = True
                    if not self.status == 'line_half_capacity':
                        self.status = 'line_half_capacity'
                        await self.run_capcacity_control()
                # line_partial_capacity
                if work['event'] == 'line_partial_capacity' or work['event'] == 'line_is_empty':
                    self.busy = False
                    self.restaurant.waiter.busy = False
                    if not self.status == work['event']:
                        self.status = work['event']

                unassigned = deque()
                while True:
                    # use assign_customer_table
                    assigned = False
                    try:
                        customer_id = self.waiting_list['queue'].popleft()
                    except IndexError:
                        self.waiting_list['queue'] = unassigned
                        break
                    if not customer_id in self.waiting_list['customers']:
                        continue
                    pref = self.waiting_list['customers'][customer_id]
                    table_type = None
                    if 'sit_together' in pref and len(pref['sit_together']) > 0:
                        # check that all customers are on waiting list, else append to end of line
                        missing_from_group = [c in self.waiting_list['customers'] for c in pref['sit_together']]
                        if False in missing_from_group:
                            unassigned.append(customer_id)
                            continue
                        seats = len(pref['sit_together']) + 1
                        group_choices = {self.waiting_list['customers'][c]['meal_choice'] for c in pref['sit_together']}
                        group_choices.add(pref['meal_choice'])

                        if 'both' in group_choices:
                            table_type = 'both'
                        elif 'dinner' in group_choices:
                            if 'dessert' in group_choices:
                                table_type = 'both'
                            else:
                                table_type = 'dinner'
                        else:
                            table_type == 'dessert'
                        
                        
                        group_ids = [customer_id,  *pref['sit_together']]

                        if 'none' in group_choices or table_type is None:
                            # refuse service - everyone must order something
                            for c_id in group_ids:
                                await self.remove_customer_from_line(c_id)
                            continue

                        for t_type in {table_type, 'open'}:
                            for t_id in self.tables[t_type]:
                                if not t_id in available_tables:
                                    continue
                                if self.tables[t_type][t_id] >= seats:
                                    # assign group to table
                                    for c_id in group_ids:
                                        await self.assign_customer_table(
                                            c_id, t_id
                                        )
                                    self.tables[t_type][t_id] -=seats
                                    assigned = True
                                    break
                            if assigned:
                                # remove group ids from wating list
                                for c_id in group_ids:
                                    m_choice = self.waiting_list['customers'][c_id]['meal_choice']
                                    self.waiting_list[m_choice].discard(c_id)
                                    del self.waiting_list['customers'][c_id]
                                    if c_id in self.waiting_list['queue']:
                                        self.waiting_list['queue'].remove(c_id)
                                break
                        if not assigned:
                            unassigned.append(customer_id)
                    
                    """
                    Non-Groups
                    prefer meal_choice type tables

                    Only allow open table usage when not busy
                    for dessert only customers
                    """
                    self.log.warning(f"{self} non-group ## cid {customer_id} pref {pref}")
                    if pref['meal_choice'] == 'none':
                        await self.remove_customer_from_line(customer_id)
                        continue
                    if self.busy and pref['meal_choice'] == 'dessert':
                        table_options = {pref['meal_choice']}
                    else:
                        table_options = {pref['meal_choice'], 'open'}
                    for t_type in table_options:
                        if not t_type in self.tables:
                            continue
                        if assigned:
                            break
                        for t_id in self.tables[t_type]:
                            if t_id in available_tables and self.tables[t_type][t_id] >= 1:
                                await self.assign_customer_table(
                                    customer_id,
                                    t_id
                                )
                                self.tables[t_type][t_id] -=1
                                m_choice = pref['meal_choice']
                                self.waiting_list[m_choice].discard(customer_id)
                                del self.waiting_list['customers'][customer_id]
                                assigned = True
                                break

                    if not assigned:
                        unassigned.append(customer_id)
        except Exception as e:
            self.log.exception(f"{self} exiting")
        self.log.warning(f"{self} exiting")

    