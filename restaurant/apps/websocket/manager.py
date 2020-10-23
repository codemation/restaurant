from fastapi import FastAPI
from fastapi.websockets import WebSocket

class ConnectionManager:
    def __init__(self, server: FastAPI):
        self.server = server
        self.log = server.log
        self.active_ws_connections = {}

    async def connect(self, websocket: WebSocket):
        return await websocket.accept()

    def store_connect(self, connection_id, websocket: WebSocket):
        self.log.warning(f"created websocket connection with connection_id {connection_id}")
        self.active_ws_connections[connection_id] = websocket
    async def send_json(self, connection_id, data):
        await self.active_ws_connections[connection_id].send_json(data)
    def disconnect(self, connection_id: str):
        self.log.warning(f"deleted websocket connection with connection_id {connection_id}")
        del self.active_ws_connections[connection_id]
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await self.active_ws_connections[connection].send_text(message)