FROM python:3.11-slim

WORKDIR /backend

COPY requirements.txt /backend/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /backend/

CMD [ "python", "ingestion.py"]
