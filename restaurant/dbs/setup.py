
async def run(server):
    server.data = dict()
            
    from dbs.restaurant import restaurant_db
    await restaurant_db.run(server)
            