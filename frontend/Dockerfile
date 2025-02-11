# Use an official lightweight Python image
FROM python:3.10-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Copy all files from your frontend project into the container
COPY . .
COPY ../configs /app/configs

# Expose port 8080 for the web server
EXPOSE 8080

# Command to start the Python HTTP server
CMD ["python3", "-m", "http.server", "8080"]
