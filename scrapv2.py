#%%
import os
import re
import time
import logging
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
import requests
from requests.adapters import HTTPAdapter, Retry

#%%
# ================================
# Configuración inicial
# ================================
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

engine = create_engine("sqlite:///github_data.db")

# Configurar session con reintentos
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504]
)
session.mount("https://", HTTPAdapter(max_retries=retries))

# Configurar logging
logging.basicConfig(
    filename="github_scan.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger().addHandler(logging.StreamHandler())  # también mostrar en consola

#%%
# ================================
# Patrones y archivos a buscar
# ================================
REGEX_PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Google API Key": r"AIza[0-9A-Za-z-_]{35}",
    "Slack Token": r"xox[baprs]-[0-9]{12}-[0-9]{12}-[0-9A-Za-z]{24}",
    "Private RSA Key": r"-----BEGIN PRIVATE KEY-----",
    "Generic Password": r"(password|passwd|pwd)\s*=\s*.+",
}

FILES_TO_SEARCH = [".env", "config.json", "settings.py", "application.properties"]

#%%
# ================================
# Funciones auxiliares
# ================================
def buscar_archivos(query, max_results=100):
    """Busca archivos en GitHub por nombre, con paginación"""
    results = []
    per_page = 25
    for page in range(1, (max_results // per_page) + 2):
        url = "https://api.github.com/search/code"
        params = {"q": f"filename:{query}", "per_page": per_page, "page": page}
        try:
            resp = session.get(url, headers=HEADERS, params=params, timeout=15)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                results.extend(items)
            elif resp.status_code == 403:
                logging.warning("Rate limit alcanzado. Durmiendo 60s...")
                time.sleep(60)
            else:
                logging.error(f"Error buscando archivos: {resp.status_code} {resp.text}")
        except Exception as e:
            logging.error(f"Error en request de GitHub: {e}")
        time.sleep(2)
    return results[:max_results]

def analizar_contenido(file_url):
    """Descarga contenido y aplica regex"""
    raw_url = file_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    findings = []
    try:
        resp = session.get(raw_url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            content = resp.text
            for name, pattern in REGEX_PATTERNS.items():
                if re.search(pattern, content):
                    findings.append(name)
        else:
            logging.warning(f"No se pudo descargar {file_url}: {resp.status_code}")
    except Exception as e:
        logging.error(f"Error descargando archivo {file_url}: {e}")
    return findings

def guardar_resultados(batch_results):
    """Guarda resultados en CSV y en SQLite"""
    if not batch_results:
        return
    df = pd.DataFrame(batch_results)
    df.to_sql("files_found", engine, if_exists="append", index=False)
    df.to_csv(
        "repos_sensitive.csv",
        mode="a",
        header=not os.path.exists("repos_sensitive.csv"),
        index=False
    )
    logging.info(f"{len(df)} registros guardados en BD y CSV")

#%%
# ================================
# Pipeline principal
# ================================
def main_loop():
    try:
        while True:
            batch_results = []
            for filetype in FILES_TO_SEARCH:
                archivos = buscar_archivos(filetype, max_results=50)
                for item in archivos:
                    repo = item["repository"]["full_name"]
                    file_path = item["path"]
                    html_url = item["html_url"]

                    findings = analizar_contenido(html_url)
                    batch_results.append({
                        "repo": repo,
                        "file": file_path,
                        "url": html_url,
                        "findings": ", ".join(findings),
                        "is_sensitive": len(findings) > 0
                    })

                    # Guardar cada 10 archivos
                    if len(batch_results) >= 10:
                        guardar_resultados(batch_results)
                        batch_results = []

            # Guardar cualquier resultado restante
            guardar_resultados(batch_results)

            logging.info("Batch completado. Durmiendo 5 minutos...")
            time.sleep(300)  # 5 minutos antes de siguiente ronda
    except KeyboardInterrupt:
        logging.info("Script detenido manualmente por usuario.")

#%%
if __name__ == "__main__":
    logging.info("Iniciando escaneo GitHub...")
    main_loop()
