# websocket
async def run(server):
    # logic to handle websocket requests
    import os, uuid, json
    from fastapi.websockets import WebSocket, WebSocketDisconnect
    from apps.websocket.manager import ConnectionManager

    log = server.log

    # PATH websocket will listen for requests
    WS_PATH = os.environ['WS_PATH']

    server.connection_manager = ConnectionManager(server)

    @server.websocket_route(WS_PATH)
    async def game(websocket: WebSocket):
        # decode auth - determine if valid & add connection
        # add connection to connection manager
        log.debug(f"game ws connection starting {websocket}")
        result = await server.connection_manager.connect(websocket)

        connection_id = str(uuid.uuid1())

        server.connection_manager.store_connect(connection_id, websocket)

        log.warning(f"websocket actions: {server.ws_action}")

        while True:
            try:
                request = await websocket.receive()
                log.warning(f"received request: {request}")
                if 'text' in request:
                    request = json.loads(request['text'])
                if 'ping' in request:
                    await websocket.send_json({'pong': 'pong'})
                if 'name' in request:
                    print(f"triggering: {request['name']}")
                    await server.ws_action[request['name']](connection_id, request['payload'])

            except Exception as e:
                log.exception(f"exception when processing request")
                server.connection_manager.disconnect(connection_id)
                break