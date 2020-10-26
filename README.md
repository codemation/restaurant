# restaurant

Restaurant Simulator

## Instructions - Getting Started 
Deploy a Restaurant Simulator instance

Required Env Vars:
- WS_PATH: Example '/ws/game1' 
    this is the path that uvicorn will allow websocket negotion with client, and where client requests to restaurant server will take place.

- MODE: Example 'mode1', 'game1'
    Essentially a lable, as not tied to path, but prevents default testing WS_PATH from being used

Example Start an Instance

    $ docker run -d --name rest_sim -p 8390:8190 -e WS_PATH='/game1' -e MODE='game1' joshjamison/restaurant_simulator:latest


### Deploy the instance

Example:

    $ git clone https://github.com/codemation/restaurant.git

    $ cd restaurant;

    (python37env)$ python test_restaurant.py 192.168.122.100 8390 /game1
    ..
    ....

    test_run results: Score: 20 / 31

## Stack
- uvicorn - ASGI Server
- FastAPI - Python Framework for quickly creating websocket / api endpoints
- aiopyql - database ORM providing cache layer for database access and reducing / eliminating access to data when possibe. 
- sqlite - no network persistent database,  to satisfy the basic schema requiremnts, and storming required persistent data.


## Scaling
The application can be scaled by simply creating new instances in front of a load-balancer(nginx). Databases will be stored in the ephemeral container storage as game data does not need to persist beyond runtime. 