FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Install python-dotenv
RUN pip install python-dotenv

CMD ["python", "countdown_bot.py"]