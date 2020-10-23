# restaurant
async def run(server):
    import asyncio
    from apps.restaurant import restaurant

    log = server.log

    server.restaurants = {}

    server.events_for_client = {}
    server.work_for_waiters = {}
    server.work_for_hostess = {}
    server.work_for_cooks = {}
    server.tables = {}
    server.lines = {}

    async def restaurant_update(connection_id, data):
        log.warning(f"restaurant update with data: {data}")
        restaurants = server.data['restaurant'].tables['restaurants']
        restaurant_id, restaurant_state = data['id'], data['state']
        # start game if new restaurant id
        
        if await restaurants[restaurant_id] == None and restaurant_state == 0:
            server.restaurants[restaurant_id] = await restaurant.Restaurant.create(
                server,
                connection_id,
                restaurant_id,
                data['tables'],
                data['dinner_prepare_time'],
                data['dessert_prepare_time'],
                data['line_number'], 
            )
            # start waiters & hostess for new restaurant
            server.event_loop.create_task(
                server.restaurants[restaurant_id].restaurant_manager()
            )
        else:
            await server.events_for_client[restaurant_id].put({
                'event': 'game_over'
            })

    server.ws_action["restaurant_update"] = restaurant_update