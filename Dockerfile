FROM python:3.10-slim
EXPOSE 8501

WORKDIR /app

COPY ./requirements.txt ./requirements.txt
RUN python -m pip install -r requirements.txt

COPY ./src src

ENTRYPOINT ["streamlit", "run", "src/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
