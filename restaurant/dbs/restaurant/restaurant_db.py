async def run(server):
    import sys, os

    async def restaurant_attach():
        config=dict()
            
        with open('.cmddir', 'r') as projDir:
            for projectPath in projDir:
                config['database'] = f'{projectPath}dbs/restaurant/restaurant'
                config['loop'] = server.event_loop
                config['debug'] = True
        #USE ENV PATH for PYQL library or /pyql/
        sys.path.append('/pyql/' if os.getenv('PYQL_PATH') == None else os.getenv('PYQL_PATH'))
        from aiopyql import data
        from . import setup
        server.data['restaurant'] = await data.Database.create(**config)
        server.data['restaurant'].enable_cache()
        await setup.attach_tables(server)
        return {"status": 200, "message": "restaurant attached successfully"}, 200
    await restaurant_attach()
            