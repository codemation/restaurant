# restaurant

Restaurant Simulator

## Instructions - Getting Started 
Deploy a Restaurant Simulator instance

    $ docker run -d --name rest_sim -p 8390:8190 -e WS_PATH='/game1' -e MODE='game1' joshjamison/restaurant_simulator:latest


### Deploy the instance

Example:

    $ git clone https://github.com/codemation/restaurant.git

    $ cd restaurant;

    (python37env)$ python test_restaurant.py 192.168.122.100 8390 /game1
    ..
    ....

    test_run results: Score: 20 / 31

