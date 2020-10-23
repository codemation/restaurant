
async def db_attach(server):

    db = server.data['restaurant']

    if 'customers' in db.tables:
        await db.run('drop table customers')

    await db.create_table(
        'customers', 
        [
            ('id', str, 'UNIQUE NOT NULL'), 
            ('restaurant_id', str),
            ('state', int, 'NOT NULL'),
            ('table_id', int),
            ('stress_level', int, 'NOT NULL'),
            ('sit_together', str), #JSON
            ('will_have_dinner', bool),
            ('will_have_dessert', bool),
            ('satisfied', bool)
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
    pass # Enter db.create_table statement here
            