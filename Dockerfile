# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Install system dependencies (ffmpeg and clean up cache)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . /app/

# Make port 5002 available to the world outside this container
EXPOSE 5002

# Run gunicorn with a shell wrapper to dynamically bind to the PORT environment variable
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-5002} --timeout 120"]
