
async def run(server):
    import os

    if os.environ.get('MODE') == None:
        os.environ['MODE'] = 'testing'

    if os.environ['MODE'] == 'testing':
        os.environ['WS_PATH'] = '/testing'

    server.ws_action = {}

    from apps.restaurant import restaurant_manager
    await restaurant_manager.run(server)            
            
    from apps.customer import customer
    await customer.run(server)            
            
    from apps.websocket import websocket
    await websocket.run(server)            
            