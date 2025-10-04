FROM python:3.11-slim

# Installer les dépendances système minimales
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Créer le répertoire de travail
WORKDIR /app

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

# Créer le répertoire de stockage local
RUN mkdir -p local_storage

# Donner les permissions d'exécution
RUN chmod +x run_bot.py setup.py

# Exposer le port (optionnel, pour monitoring)
EXPOSE 8080

# Commande par défaut
CMD ["python", "run_bot.py"]