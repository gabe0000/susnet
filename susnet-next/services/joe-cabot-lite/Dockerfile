FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY joe_cabot_lite.py .
CMD ["python", "/app/joe_cabot_lite.py"]
