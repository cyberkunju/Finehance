FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
ARG UID=1000
ARG GID=1000
RUN groupadd --gid ${GID} appuser \
    && useradd --uid ${UID} --gid ${GID} --shell /bin/bash --create-home appuser

# Install Poetry
RUN pip install poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create virtual environment
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY --chown=appuser:appuser . .

# Install the application
RUN poetry install --no-interaction --no-ansi

# Create models directory with correct ownership
RUN mkdir -p /app/models && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
