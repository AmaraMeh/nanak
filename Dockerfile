FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \n    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -U pip 
    && pip install --no-cache-dir -r requirements.txt
COPY . /app

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "elearning_bot.runner"]
