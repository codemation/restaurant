
async def db_attach(server):
    db = server.data['restaurant']
    if not 'restaurants' in db.tables:
        await db.create_table(
            'restaurants', 
            [
                ('id', str, 'UNIQUE NOT NULL'), 
                ('state', int),
                ('tables', int),
                ('dinner_prepare_time', int),
                ('dessert_prepare_time', int),
                ('line_number', int)
            ],
            'id',
            cache_enabled=True
        )
    pass # Enter db.create_table statement here
            