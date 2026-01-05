FROM python:3.12-slim

WORKDIR /app

# Copy dependency list
COPY requirements.txt ./

# Install dependencies, including gunicorn
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Set environment variables
ARG VITE_BACKEND_PORT=8010
ENV VITE_BACKEND_PORT=${VITE_BACKEND_PORT}

EXPOSE ${BACKEND_PORT}

# Run gunicorn
CMD ["sh", "-c", "gunicorn --workers=1 --timeout=120 --preload backend.wsgi:application --bind 0.0.0.0:${VITE_BACKEND_PORT}"]
