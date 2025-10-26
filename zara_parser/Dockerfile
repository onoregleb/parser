# Dockerfile для Zara API Parser
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файлы парсера
COPY simple_parser.py .
COPY config.json .

# Создаем директории для данных
RUN mkdir -p /app/data
RUN mkdir -p /app/logs

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV ZARA_DATA_DIR=/app/data
ENV ZARA_LOG_DIR=/app/logs

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 parser && chown -R parser:parser /app
USER parser

# Запускаем парсер
CMD ["python", "simple_parser.py"]
