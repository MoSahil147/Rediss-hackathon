# Stage 1: The Builder Stage
# This stage installs all dependencies and pre-downloads the ML models.
FROM python:3.10-slim AS builder

# Set an environment variable to prevent interactive prompts.
ENV DEBIAN_FRONTEND=noninteractive

# Install all necessary system dependencies.
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    # For pytesseract
    tesseract-ocr libtesseract-dev libleptonica-dev pkg-config \
    # For opencv-python
    libgl1 libglib2.0-0 \
    # For fitz/PyMuPDF
    libmupdf-dev && \
    # Clean up apt cache to reduce image size.
    rm -rf /var/lib/apt/lists/*

# Set the working directory.
WORKDIR /app

# Install uv using pip.
RUN pip install uv

# Copy requirements and the model pre-loader script.
COPY requirements.txt preload_models.py ./

# Create a virtual environment and install Python packages using uv.
# This will now install the CPU-only version of PyTorch.
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install --no-cache-dir --index-strategy unsafe-best-match -r requirements.txt

# === NEW STEP: PRE-LOAD THE MODELS ===
# This runs the script to download the models into the builder's cache.
# By default, this cache is at /root/.cache
RUN . .venv/bin/activate && python preload_models.py


# Stage 2: The Final Production Stage
# This stage creates the final, minimal image with everything pre-loaded.
FROM python:3.10-slim AS final

ENV DEBIAN_FRONTEND=noninteractive

# Install ONLY the runtime system dependencies.
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    tesseract-ocr libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Create a non-privileged user and group for security.
# Also create a home directory for the user to store the cache.
RUN addgroup --system app && adduser --system --group --home /home/app app

# Set the home directory for the sentence-transformers library to find its cache.
ENV SENTENCE_TRANSFORMERS_HOME=/home/app/.cache/torch/sentence_transformers

WORKDIR /app

# Copy the virtual environment from the builder stage.
COPY --from=builder /app/.venv ./.venv

# === NEW STEP: COPY THE PRE-LOADED MODEL CACHE ===
# Copy the cache from the builder stage to the final image.
COPY --from=builder /root/.cache /home/app/.cache

# Copy your application code into the final image.
COPY . .

# Activate the virtual environment by adding it to the PATH.
ENV PATH="/app/.venv/bin:$PATH"

# Set correct ownership for all application files and the cache.
RUN chown -R app:app /app && \
    chown -R app:app /home/app

# Switch to the non-root user.
USER app

# Define the production command to run your application.
# Replace 'fastapi_server:app' with your file and app instance.
CMD ["uvicorn", "fastapi_server:app", "--host", "0.0.0.0", "--port", "8080"]

# # Stage 1: Builder
# FROM python:3.10-slim AS builder

# ENV DEBIAN_FRONTEND=noninteractive

# # Install build-time system dependencies
# RUN apt-get update && \
#     apt-get install --no-install-recommends -y \
#     tesseract-ocr libtesseract-dev libleptonica-dev pkg-config \
#     libgl1 libglib2.0-0 \
#     libmupdf-dev && \
#     rm -rf /var/lib/apt/lists/*

# WORKDIR /app

# # Install uv
# RUN pip install uv

# # Copy requirements and preload script
# COPY requirements.txt preload_models.py ./

# # Create venv and install deps
# RUN uv venv && \
#     . .venv/bin/activate && \
#     uv pip install --no-cache-dir --index-strategy unsafe-best-match -r requirements.txt

# # Preload models into cache
# RUN . .venv/bin/activate && python preload_models.py

# # (Optional) Clean pip cache, but keep torch/transformers cache
# RUN rm -rf /root/.cache/pip


# # Stage 2: Runtime
# FROM python:3.10-slim AS final

# ENV DEBIAN_FRONTEND=noninteractive

# # Runtime-only system deps
# RUN apt-get update && \
#     apt-get install --no-install-recommends -y \
#     tesseract-ocr libgl1 libglib2.0-0 && \
#     rm -rf /var/lib/apt/lists/*

# # Create non-root user
# RUN addgroup --system app && adduser --system --group --home /home/app app

# # Set sentence-transformers cache dir
# ENV SENTENCE_TRANSFORMERS_HOME=/home/app/.cache/torch/sentence_transformers

# WORKDIR /app

# # Copy venv and cache, then fix permissions
# COPY --from=builder /app/.venv ./.venv
# COPY --from=builder /root/.cache /home/app/.cache

# # Copy application code
# COPY . .

# # Ensure correct ownership for all files
# RUN chown -R app:app /app && \
#     chown -R app:app /home/app

# # Activate venv
# ENV PATH="/app/.venv/bin:$PATH"

# USER app

# # Start the app
# CMD ["uvicorn", "fastapi_server:app", "--host", "0.0.0.0", "--port", "8080"]