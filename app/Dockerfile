FROM python:3.12 AS builder
WORKDIR /src
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .


# Expose the port the app runs on
EXPOSE 80

# Command to run the application
CMD ["gunicorn", "-w", "2", "-b", "[::]:80", "main:app"]
