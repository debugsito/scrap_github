#%%
import os
import requests
import re
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
#%%
# ==================================
# 1. Configuración inicial
# ==================================
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}
#%%
# Regex para detectar secretos
REGEX_PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Google API Key": r"AIza[0-9A-Za-z-_]{35}",
    "Slack Token": r"xox[baprs]-[0-9]{12}-[0-9]{12}-[0-9A-Za-z]{24}",
    "Private RSA Key": r"-----BEGIN PRIVATE KEY-----",
    "Generic Password": r"(password|passwd|pwd)\s*=\s*.+",
}

# Archivos de interés
FILES_TO_SEARCH = [".env", "config.json", "settings.py", "application.properties"]
#%%
# Crear conexión SQLite (archivo github_data.db en el proyecto)
engine = create_engine("sqlite:///github_data.db")

#%%
# ==================================
# 2. Funciones auxiliares
# ==================================
def buscar_archivos(query, max_results=5):
    """Busca archivos en GitHub por nombre"""
    url = "https://api.github.com/search/code"
    params = {"q": f"filename:{query}", "per_page": max_results}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code == 200:
        return response.json().get("items", [])
    else:
        print("Error:", response.status_code, response.text)
        return []

def analizar_contenido(file_url):
    """Descarga contenido y aplica regex"""
    raw_url = file_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    try:
        resp = requests.get(raw_url, headers=HEADERS)
        if resp.status_code == 200:
            content = resp.text
            findings = []
            for name, pattern in REGEX_PATTERNS.items():
                if re.search(pattern, content):
                    findings.append(name)
            return content, findings
    except Exception as e:
        print("Error descargando archivo:", e)
    return None, []
#%%
# ==================================
# 3. Pipeline de búsqueda y análisis
# ==================================
results = []

for filetype in FILES_TO_SEARCH:
    archivos = buscar_archivos(filetype, max_results=25)  # limitar resultados en prueba
    for item in archivos:
        repo = item["repository"]["full_name"]
        file_path = item["path"]
        html_url = item["html_url"]

        content, findings = analizar_contenido(html_url)
        results.append({
            "repo": repo,
            "file": file_path,
            "url": html_url,
            "findings": ", ".join(findings),
            "is_sensitive": len(findings) > 0
        })

# Convertir a DataFrame
df = pd.DataFrame(results)

#%%
# ==================================
# 4. Guardar en la base de datos
# ==================================
if not df.empty:
    df.to_csv("repos_sensitive.csv", index=False)
    df.to_sql("files_found", engine, if_exists="append", index=False)
    print(f"{len(df)} registros insertados en la BD")
else:
    print("No se encontraron resultados para este batch.")