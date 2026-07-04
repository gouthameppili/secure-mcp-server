# 1. Use the official lightweight Python image to save space
FROM python:3.12-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy the requirements file first to leverage Docker caching
COPY requirements.txt .

# 4. Install dependencies without keeping the package cache to save memory
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the backend application code
COPY . .

# 6. Expose the default port
EXPOSE 8000

# 7. Start the server bound to 0.0.0.0 with 1 worker to stay under the 512MB RAM limit
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]