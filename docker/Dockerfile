FROM joshjamison/python37:latest

ENV PATH="$V_ENV/bin:$PATH"

RUN git clone https://github.com/codemation/restaurant.git

WORKDIR /restaurant

RUN pip install -r /restaurant/requirements.txt

WORKDIR /restaurant/restaurant

EXPOSE 8190

CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8190", "server:app"]