
async def db_attach(server):
    db = server.data['restaurant']
    if not 'tables' in db.tables:
        await db.create_table(
            'tables', 
            [
                ('id', str, 'UNIQUE NOT NULL'),
                ('table_id', int),
                ('restaurant_id', str),
                ('available', bool)
            ],
            'id',
            foreign_key={
                'restaurant_id': {
                    'table': 'restaurants',
                    'ref': 'id',
                    'mods': 'ON UPDATE CASCADE ON DELETE CASCADE'
                }
            },
            cache_enabled=True
        )
            