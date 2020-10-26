def run(server):
    import os
    import uvloop
    import asyncio

    #asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    server.event_loop = asyncio.get_event_loop()
    #server.event_loop.set_debug(True)
    try:
        cmddirPath = None
        realPath = None
        with open('./.cmddir', 'r') as cmddir:
            for line in cmddir:
                cmddirPath = line
            realPath = str(os.path.realpath(cmddir.name)).split('.cmddir')[0]
        if not realPath == cmddirPath:
            print(f"NOTE: Project directory may have moved, updating project cmddir files from {cmddirPath} -> {realPath}")
            import os
            os.system("find . -name .cmddir > .proj_cmddirs")
            with open('.proj_cmddirs', 'r') as projCmdDirs:
                for f in projCmdDirs:
                    with open(f.rstrip(), 'w') as projCmd:
                        projCmd.write(realPath)
    except Exception as e:
        print("encountered exception when checking projPath")
        print(repr(e))
    async def setup():
        server.PYQL_DEBUG = os.environ.get('PYQL_DEBUG')

        from logs import setup as log_setup
        log_setup.run(server)

        from dbs import setup as dbsetup
        await dbsetup.run(server) 

        from apps import setup
        await setup.run(server)

    server.event_loop.create_task(
        setup()
    )
                