FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy application code and scripts
COPY . .

# Ensure scripts are executable
RUN chmod +x migrate_db.py startup.py

# Create directory for SQLite database
RUN mkdir -p /app/data

# Set environment variables
ENV FLASK_APP=app.py
ENV DATABASE_URL=sqlite:////app/data/discord_summaries.db
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Use Python startup script
CMD ["python", "startup.py"]