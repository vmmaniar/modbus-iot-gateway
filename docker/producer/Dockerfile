FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (Docker layer cache)
COPY simulator/requirements.txt /tmp/req.txt
RUN pip install --no-cache-dir -r /tmp/req.txt paho-mqtt==2.1.0

# Copy the project sources. We mount the whole repo so the producer can
# import simulator.* directly without a package install step.
COPY . /app

# Make Python treat the repo root as the import base
ENV PYTHONPATH=/app

# Default to running the producer service; docker-compose overrides this for tcp-slave.
CMD ["python", "-m", "docker.producer.producer"]
