# Use an official Python runtime as a parent image.
FROM python:3.12-slim

# Set the working directory in the container.
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Command to run the message consumer
CMD ["python", "message_consumer.py"]