# TODO: use uv native docker image
FROM python:3.10-slim-bookworm

# Install curl to download uv
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

# Install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh

RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin/:$PATH"
# Set the working directory
WORKDIR /app

# # Copy the project files into the container
COPY pyproject.toml /app

# # Install dependencies
RUN uv sync

COPY . .

COPY ../configs /app/configs
# # Expose the application port
EXPOSE 8000

# # Command to run the application
CMD ["uv", "run", "server.py"]
