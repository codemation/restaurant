# customer
async def run(server):

    log = server.log

    async def customer_update(connection_id, data):
        log.warning(f"starting customer_update with {data}")
        customers = server.data['restaurant'].tables['customers']
        # new customer
        if data['state'] == 0:
            data['sit_together'] = {'sit_together': data['sit_together']}
            await customers.insert(**data)
        else:
            customer_id = data.pop('id')
            await customers.update(
                **data,
                where={'id': customer_id}
            )

    server.ws_action["customer_update"] = customer_update