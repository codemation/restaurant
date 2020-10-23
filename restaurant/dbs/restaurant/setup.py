 # restaurant
async def attach_tables(server):
    #Tables are added  here
    from dbs.restaurant.tables import restaurant
    await restaurant.db_attach(server)
            
    from dbs.restaurant.tables import customers
    await customers.db_attach(server)
            
    from dbs.restaurant.tables import tables
    await tables.db_attach(server)