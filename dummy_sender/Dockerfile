FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto ./proto
COPY dummy_sender/dummy_sender.py .

CMD ["python", "dummy_sender.py"]