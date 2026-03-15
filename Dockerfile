FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV ZEEBE_GATEWAY_ADDRESS=zeebe:26500
ENV API_PORT=5000

CMD ["python", "api/workflow_trigger_api.py"]
