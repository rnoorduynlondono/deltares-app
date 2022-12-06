FROM rnlondono/python-db2:latest
EXPOSE 8501

WORKDIR /app

COPY ./requirements.txt ./requirements.txt
COPY ./measuremap.csv ./measuremap.csv

RUN python -m pip install -r requirements.txt

COPY ./src src

ENTRYPOINT ["streamlit", "run", "src/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
