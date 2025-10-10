# Utiliser l'image Python officielle
FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Copier le fichier requirements.txt
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier l'application
COPY app.py .

# Exposer le port par défaut de Streamlit
EXPOSE 8501

# Configuration de Streamlit
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Commande pour lancer l'application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

