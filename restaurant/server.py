from fastapi import FastAPI
app = FastAPI()

import setup
setup.run(app)