#!/usr/bin/env python3
"""
GitHub Repository Data Collector
Extrae metadatos masivos de repositorios con archivos de configuración sensibles
Optimizado para ejecución continua por días
"""

import os
import sys
import time
import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Set
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# ================================
# Configuración y Constantes
# ================================
load_dotenv()


@dataclass
class Config:
    github_token: str = os.getenv("GITHUB_TOKEN")
    db_path: str = "github_repos_data.db"
    csv_path: str = "github_repos_extracted.csv"
    log_path: str = "github_collector.log"
    batch_size: int = 50
    delay_between_requests: float = 0.72  # Para respetar rate limits
    delay_between_batches: int = 300  # 5 minutos
    max_repos_per_search: int = 1000
    backup_interval_hours: int = 6
    # Filtros temporales para repositorios recientes
    years_back: int = 2  # Buscar repos de los últimos N años
    min_stars: int = 0  # Mínimo de estrellas (0 = todos)
    min_size: int = 0  # Tamaño mínimo en KB (0 = todos)
    exclude_forks: bool = True  # Excluir forks para datos originales


# Archivos objetivo para detectar configuraciones sensibles
TARGET_FILES = [
    ".env", ".env.local", ".env.production", ".env.development",
    "config.json", "config.yaml", "config.yml", "app.config",
    "settings.py", "settings.json", "local_settings.py",
    "application.properties", "application.yml", "application.yaml",
    "secrets.json", "credentials.json", "auth.json",
    "docker-compose.yml", "docker-compose.yaml",
    ".aws/credentials", ".aws/config",
    "firebase-adminsdk.json", "service-account.json",
    "id_rsa", "id_rsa.pub", ".ssh/config",
    ".htpasswd", ".htaccess"
]

# Lenguajes de programación principales para filtrar
PROGRAMMING_LANGUAGES = [
    "JavaScript", "Python", "Java", "TypeScript", "C#", "PHP", "C++", "C",
    "Shell", "Go", "Ruby", "Kotlin", "Swift", "Rust", "Scala", "Dart"
]


@dataclass
class RepositoryData:
    """Estructura de datos del repositorio"""
    id: int
    name: str
    full_name: str
    owner_login: str
    owner_type: str
    private: bool
    html_url: str
    description: Optional[str]
    fork: bool
    created_at: str
    updated_at: str
    pushed_at: Optional[str]
    size: int
    stargazers_count: int
    watchers_count: int
    language: Optional[str]
    forks_count: int
    archived: bool
    disabled: bool
    open_issues_count: int
    license_name: Optional[str]
    default_branch: str
    topics: str  # JSON string
    has_issues: bool
    has_projects: bool
    has_wiki: bool
    has_pages: bool
    has_downloads: bool
    visibility: str
    # Datos adicionales del owner
    owner_id: int
    owner_location: Optional[str]
    owner_company: Optional[str]
    owner_public_repos: Optional[int]
    owner_followers: Optional[int]
    # Metadatos de archivos sensibles encontrados
    sensitive_files: str  # JSON string con archivos encontrados
    sensitive_files_count: int
    extraction_timestamp: str


class GitHubCollector:
    def __init__(self, config: Config):
        self.config = config
        self.session = self._setup_session()
        self.db_connection = self._setup_database()
        self.logger = self._setup_logging()
        self.processed_repos: Set[int] = set()
        self.stats = {
            'repos_processed': 0,
            'files_found': 0,
            'api_calls': 0,
            'start_time': datetime.now()
        }
        self._load_processed_repos()

    def _setup_session(self) -> requests.Session:
        """Configura sesión HTTP con reintentos"""
        session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[403, 429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.headers.update({
            "Authorization": f"token {self.config.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Security-Research-Bot"
        })
        return session

    def _setup_database(self) -> sqlite3.Connection:
        """Inicializa base de datos SQLite"""
        conn = sqlite3.connect(self.config.db_path, check_same_thread=False)

        # Crear tabla principal de repositorios
        conn.execute("""
                     CREATE TABLE IF NOT EXISTS repositories
                     (
                         id
                         INTEGER
                         PRIMARY
                         KEY,
                         name
                         TEXT,
                         full_name
                         TEXT
                         UNIQUE,
                         owner_login
                         TEXT,
                         owner_type
                         TEXT,
                         private
                         BOOLEAN,
                         html_url
                         TEXT,
                         description
                         TEXT,
                         fork
                         BOOLEAN,
                         created_at
                         TEXT,
                         updated_at
                         TEXT,
                         pushed_at
                         TEXT,
                         size
                         INTEGER,
                         stargazers_count
                         INTEGER,
                         watchers_count
                         INTEGER,
                         language
                         TEXT,
                         forks_count
                         INTEGER,
                         archived
                         BOOLEAN,
                         disabled
                         BOOLEAN,
                         open_issues_count
                         INTEGER,
                         license_name
                         TEXT,
                         default_branch
                         TEXT,
                         topics
                         TEXT,
                         has_issues
                         BOOLEAN,
                         has_projects
                         BOOLEAN,
                         has_wiki
                         BOOLEAN,
                         has_pages
                         BOOLEAN,
                         has_downloads
                         BOOLEAN,
                         visibility
                         TEXT,
                         owner_id
                         INTEGER,
                         owner_location
                         TEXT,
                         owner_company
                         TEXT,
                         owner_public_repos
                         INTEGER,
                         owner_followers
                         INTEGER,
                         sensitive_files
                         TEXT,
                         sensitive_files_count
                         INTEGER,
                         extraction_timestamp
                         TEXT,
                         UNIQUE
                     (
                         id
                     )
                         )
                     """)

        # Crear tabla de estadísticas
        conn.execute("""
                     CREATE TABLE IF NOT EXISTS collection_stats
                     (
                         id
                         INTEGER
                         PRIMARY
                         KEY
                         AUTOINCREMENT,
                         timestamp
                         TEXT,
                         repos_processed
                         INTEGER,
                         files_found
                         INTEGER,
                         api_calls
                         INTEGER,
                         duration_minutes
                         INTEGER
                     )
                     """)

        conn.commit()
        return conn

    def _setup_logging(self) -> logging.Logger:
        """Configura sistema de logging"""
        logger = logging.getLogger("GitHubCollector")
        logger.setLevel(logging.INFO)

        # Handler para archivo
        file_handler = logging.FileHandler(self.config.log_path)
        file_handler.setLevel(logging.INFO)

        # Handler para consola
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Formato
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def _load_processed_repos(self):
        """Carga IDs de repos ya procesados para evitar duplicados"""
        try:
            cursor = self.db_connection.execute("SELECT id FROM repositories")
            self.processed_repos = {row[0] for row in cursor.fetchall()}
            self.logger.info(f"Cargados {len(self.processed_repos)} repos previamente procesados")
        except Exception as e:
            self.logger.error(f"Error cargando repos procesados: {e}")

    def _make_github_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Realiza petición a GitHub API con manejo de errores"""
        try:
            self.stats['api_calls'] += 1
            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                # Rate limit
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                current_time = int(time.time())
                wait_time = max(reset_time - current_time, 60)
                self.logger.warning(f"Rate limit alcanzado. Esperando {wait_time}s")
                time.sleep(wait_time)
                return self._make_github_request(url, params)  # Reintentar
            elif response.status_code == 422:
                self.logger.warning(f"Query muy complejo: {url}")
                return None
            else:
                self.logger.error(f"Error API GitHub: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error en petición HTTP: {e}")
            return None

    def search_repositories_by_file(self, filename: str) -> List[Dict]:
        """Busca repositorios que contengan un archivo específico con filtros temporales simplificados"""
        repositories = []
        per_page = 100
        max_pages = self.config.max_repos_per_search // per_page

        # Calcular fecha límite para repositorios recientes
        cutoff_date = (datetime.now() - timedelta(days=365 * self.config.years_back)).strftime("%Y-%m-%d")

        for page in range(1, max_pages + 1):
            # Query simplificada - solo los filtros más importantes
            query_parts = [f"filename:{filename}"]

            # Solo agregar filtro temporal (el más importante)
            #query_parts.append(f"created:>{cutoff_date}")

            # Si exclude_forks está habilitado, agregarlo
            if self.config.exclude_forks:
                query_parts.append("fork:false")

            # Nota: Removemos filtros de stars y size para evitar queries complejas
            # Estos se pueden filtrar después en el procesamiento

            query = " ".join(query_parts)

            params = {
                "q": query,
                "type": "Code",
                "per_page": per_page,
                "page": page,
                "sort": "updated",  # Ordenar por últimas actualizaciones
                "order": "desc"
            }

            self.logger.debug(f"Query GitHub: {query}")
            data = self._make_github_request("https://api.github.com/search/code", params)

            if not data or "items" not in data:
                self.logger.warning(f"No se obtuvieron resultados para {filename} página {page}")
                break

            new_repos_count = 0
            for item in data["items"]:
                repo_data = item.get("repository", {})
                repo_id = repo_data.get("id")

                # Aplicar filtros post-query para evitar complejidad en GitHub
                if self._passes_quality_filters(repo_data) and repo_id not in self.processed_repos:
                    repositories.append({
                        **repo_data,
                        "found_file": filename,
                        "file_path": item.get("path", "")
                    })
                    new_repos_count += 1

            self.logger.info(f"Página {page}: {new_repos_count} repos nuevos de {len(data['items'])} encontrados")

            if len(data["items"]) < per_page:
                break  # No más resultados

            time.sleep(self.config.delay_between_requests)

        self.logger.info(f"Total repos nuevos encontrados para {filename}: {len(repositories)}")
        return repositories

    def _passes_quality_filters(self, repo_data: Dict) -> bool:
        """Aplica filtros de calidad después de la búsqueda para evitar queries complejas"""
        # Filtro de estrellas mínimas
        if self.config.min_stars > 0:
            stars = repo_data.get("stargazers_count", 0)
            if stars < self.config.min_stars:
                return False

        # Filtro de tamaño mínimo
        if self.config.min_size > 0:
            size = repo_data.get("size", 0)
            if size < self.config.min_size:
                return False

        return True

    def get_repository_details(self, repo_full_name: str) -> Optional[Dict]:
        """Obtiene detalles completos del repositorio"""
        url = f"https://api.github.com/repos/{repo_full_name}"
        return self._make_github_request(url)

    def get_owner_details(self, owner_login: str) -> Optional[Dict]:
        """Obtiene detalles del propietario del repositorio"""
        url = f"https://api.github.com/users/{owner_login}"
        return self._make_github_request(url)

    def search_sensitive_files_in_repo(self, repo_full_name: str) -> List[str]:
        """Busca archivos sensibles en un repositorio específico"""
        found_files = []

        for filename in TARGET_FILES:
            query = f"repo:{repo_full_name} filename:{filename}"
            params = {"q": query, "type": "Code", "per_page": 10}

            data = self._make_github_request("https://api.github.com/search/code", params)
            if data and "items" in data:
                for item in data["items"]:
                    found_files.append({
                        "filename": filename,
                        "path": item.get("path", ""),
                        "sha": item.get("sha", "")
                    })

            time.sleep(self.config.delay_between_requests)

        return found_files

    def process_repository(self, repo_data: Dict) -> Optional[RepositoryData]:
        """Procesa un repositorio y extrae todos los metadatos"""
        try:
            repo_id = repo_data.get("id")
            if repo_id in self.processed_repos:
                return None

            full_name = repo_data.get("full_name")
            if not full_name:
                return None

            self.logger.info(f"Procesando repositorio: {full_name}")

            # Obtener detalles completos del repositorio
            detailed_repo = self.get_repository_details(full_name)
            if not detailed_repo:
                return None

            # Obtener detalles del propietario
            owner_login = detailed_repo.get("owner", {}).get("login")
            owner_details = self.get_owner_details(owner_login) if owner_login else {}

            # Buscar archivos sensibles
            sensitive_files = self.search_sensitive_files_in_repo(full_name)

            # Crear objeto de datos
            repo_obj = RepositoryData(
                id=detailed_repo.get("id"),
                name=detailed_repo.get("name"),
                full_name=detailed_repo.get("full_name"),
                owner_login=detailed_repo.get("owner", {}).get("login"),
                owner_type=detailed_repo.get("owner", {}).get("type"),
                private=detailed_repo.get("private", False),
                html_url=detailed_repo.get("html_url"),
                description=detailed_repo.get("description"),
                fork=detailed_repo.get("fork", False),
                created_at=detailed_repo.get("created_at"),
                updated_at=detailed_repo.get("updated_at"),
                pushed_at=detailed_repo.get("pushed_at"),
                size=detailed_repo.get("size", 0),
                stargazers_count=detailed_repo.get("stargazers_count", 0),
                watchers_count=detailed_repo.get("watchers_count", 0),
                language=detailed_repo.get("language"),
                forks_count=detailed_repo.get("forks_count", 0),
                archived=detailed_repo.get("archived", False),
                disabled=detailed_repo.get("disabled", False),
                open_issues_count=detailed_repo.get("open_issues_count", 0),
                license_name=detailed_repo.get("license", {}).get("name") if detailed_repo.get("license") else None,
                default_branch=detailed_repo.get("default_branch"),
                topics=json.dumps(detailed_repo.get("topics", [])),
                has_issues=detailed_repo.get("has_issues", False),
                has_projects=detailed_repo.get("has_projects", False),
                has_wiki=detailed_repo.get("has_wiki", False),
                has_pages=detailed_repo.get("has_pages", False),
                has_downloads=detailed_repo.get("has_downloads", False),
                visibility=detailed_repo.get("visibility", "public"),
                owner_id=owner_details.get("id"),
                owner_location=owner_details.get("location"),
                owner_company=owner_details.get("company"),
                owner_public_repos=owner_details.get("public_repos"),
                owner_followers=owner_details.get("followers"),
                sensitive_files=json.dumps(sensitive_files),
                sensitive_files_count=len(sensitive_files),
                extraction_timestamp=datetime.now().isoformat()
            )

            self.stats['repos_processed'] += 1
            self.stats['files_found'] += len(sensitive_files)
            self.processed_repos.add(repo_id)

            return repo_obj

        except Exception as e:
            self.logger.error(f"Error procesando repositorio {repo_data.get('full_name')}: {e}")
            return None

    def save_repository_data(self, repo_data: RepositoryData):
        """Guarda datos del repositorio en BD y CSV"""
        try:
            # Insertar en SQLite
            data_dict = asdict(repo_data)
            columns = ", ".join(data_dict.keys())
            placeholders = ", ".join(["?" for _ in data_dict.keys()])

            self.db_connection.execute(
                f"INSERT OR REPLACE INTO repositories ({columns}) VALUES ({placeholders})",
                list(data_dict.values())
            )
            self.db_connection.commit()

            # Agregar a CSV
            df = pd.DataFrame([data_dict])
            df.to_csv(
                self.config.csv_path,
                mode='a',
                header=not Path(self.config.csv_path).exists(),
                index=False
            )

        except Exception as e:
            self.logger.error(f"Error guardando datos: {e}")

    def save_stats(self):
        """Guarda estadísticas de la sesión"""
        duration = (datetime.now() - self.stats['start_time']).total_seconds() / 60
        self.db_connection.execute(
            """INSERT INTO collection_stats
                   (timestamp, repos_processed, files_found, api_calls, duration_minutes)
               VALUES (?, ?, ?, ?, ?)""",
            (datetime.now().isoformat(), self.stats['repos_processed'],
             self.stats['files_found'], self.stats['api_calls'], duration)
        )
        self.db_connection.commit()

    def create_backup(self):
        """Crea backup de la base de datos"""
        backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        try:
            backup_conn = sqlite3.connect(backup_path)
            self.db_connection.backup(backup_conn)
            backup_conn.close()
            self.logger.info(f"Backup creado: {backup_path}")
        except Exception as e:
            self.logger.error(f"Error creando backup: {e}")

    def print_stats(self):
        """Imprime estadísticas actuales"""
        duration = datetime.now() - self.stats['start_time']
        cutoff_date = (datetime.now() - timedelta(days=365 * self.config.years_back)).strftime("%Y-%m-%d")

        self.logger.info(f"""
        === ESTADÍSTICAS DE EJECUCIÓN ===
        Tiempo ejecutándose: {duration}
        Filtro temporal: Repos creados después de {cutoff_date}
        Repositorios procesados: {self.stats['repos_processed']}
        Archivos sensibles encontrados: {self.stats['files_found']}
        Llamadas API realizadas: {self.stats['api_calls']}
        Repositorios únicos en BD: {len(self.processed_repos)}
        Configuración: {self.config.years_back} años, min_stars={self.config.min_stars}, exclude_forks={self.config.exclude_forks}
        """)

    def check_token_type_and_limits(self) -> Dict:
        """Verifica tipo de token y límites disponibles"""
        try:
            # Obtener información del rate limit actual
            rate_limit_data = self._make_github_request("https://api.github.com/rate_limit")
            if not rate_limit_data:
                return {"error": "No se pudo obtener información de rate limit"}

            core_limit = rate_limit_data.get("resources", {}).get("core", {})
            search_limit = rate_limit_data.get("resources", {}).get("search", {})

            # Obtener información del usuario
            user_data = self._make_github_request("https://api.github.com/user")
            if not user_data:
                return {"error": "No se pudo obtener información del usuario"}

            # Determinar tipo de cuenta basado en límites
            core_limit_total = core_limit.get("limit", 0)
            search_limit_total = search_limit.get("limit", 0)

            token_info = {
                "username": user_data.get("login"),
                "account_type": user_data.get("type", "User"),
                "plan": user_data.get("plan", {}).get("name", "free"),
                "core_limit": core_limit_total,
                "search_limit": search_limit_total,
                "core_remaining": core_limit.get("remaining", 0),
                "search_remaining": search_limit.get("remaining", 0),
                "core_reset": datetime.fromtimestamp(core_limit.get("reset", 0)).isoformat(),
                "search_reset": datetime.fromtimestamp(search_limit.get("reset", 0)).isoformat()
            }

            # Clasificar tipo de token basado en límites conocidos
            if core_limit_total >= 15000:
                token_info["token_type"] = "GitHub Enterprise Cloud"
                token_info["recommended_delay"] = 0.24  # ~15000/hour = 4.17/sec
            elif core_limit_total >= 5000:
                token_info["token_type"] = "Personal Access Token (Authenticated)"
                token_info["recommended_delay"] = 0.72  # ~5000/hour = 1.39/sec
            elif core_limit_total >= 1000:
                token_info["token_type"] = "GitHub App Installation"
                token_info["recommended_delay"] = 3.6  # ~1000/hour = 0.28/sec
            else:
                token_info["token_type"] = "Free/Unauthenticated"
                token_info["recommended_delay"] = 60  # ~60/hour = 0.017/sec

            return token_info

        except Exception as e:
            self.logger.error(f"Error verificando token: {e}")
            return {"error": str(e)}

    def optimize_delays_for_token(self, token_info: Dict):
        """Ajusta automáticamente los delays basado en el tipo de token"""
        if "recommended_delay" in token_info:
            recommended = token_info["recommended_delay"]
            current = self.config.delay_between_requests

            if recommended < current:
                self.logger.info(f"🚀 Optimización: Tu token permite delays menores")
                self.logger.info(f"   Actual: {current}s → Recomendado: {recommended}s")
                self.logger.info(f"   Para usar, modifica: delay_between_requests = {recommended}")
            else:
                self.logger.info(f"✅ Delay actual ({current}s) es apropiado para tu token")

    def print_token_info(self, token_info: Dict):
        """Muestra información detallada del token"""
        if "error" in token_info:
            self.logger.error(f"❌ Error verificando token: {token_info['error']}")
            return

        self.logger.info(f"""
        === INFORMACIÓN DEL TOKEN GITHUB ===
        👤 Usuario: {token_info.get('username')}
        🏢 Tipo de cuenta: {token_info.get('account_type')}
        💳 Plan: {token_info.get('plan')}
        🔑 Tipo de token: {token_info.get('token_type')}

        📊 LÍMITES DE API:
        Core API: {token_info.get('core_remaining')}/{token_info.get('core_limit')} por hora
        Search API: {token_info.get('search_remaining')}/{token_info.get('search_limit')} por hora

        ⏰ RESET:
        Core: {token_info.get('core_reset')}
        Search: {token_info.get('search_reset')}

        ⚡ RECOMENDACIÓN:
        Delay óptimo: {token_info.get('recommended_delay', 'N/A')}s entre requests
        """)

    def check_resume_capability(self):
        """Verifica y reporta capacidad de continuidad"""
        existing_repos = len(self.processed_repos)
        if existing_repos > 0:
            self.logger.info(f"🔄 MODO CONTINUACIÓN: {existing_repos} repos ya procesados serán omitidos")

            # Mostrar últimos repos procesados
            cursor = self.db_connection.execute(
                "SELECT full_name, extraction_timestamp FROM repositories ORDER BY extraction_timestamp DESC LIMIT 5"
            )
            recent_repos = cursor.fetchall()

            self.logger.info("📋 Últimos repositorios procesados:")
            for repo_name, timestamp in recent_repos:
                self.logger.info(f"  - {repo_name} ({timestamp})")
        else:
            self.logger.info("🆕 MODO INICIAL: Empezando extracción desde cero")
        """Verifica y reporta capacidad de continuidad"""
        existing_repos = len(self.processed_repos)
        if existing_repos > 0:
            self.logger.info(f"🔄 MODO CONTINUACIÓN: {existing_repos} repos ya procesados serán omitidos")

            # Mostrar últimos repos procesados
            cursor = self.db_connection.execute(
                "SELECT full_name, extraction_timestamp FROM repositories ORDER BY extraction_timestamp DESC LIMIT 5"
            )
            recent_repos = cursor.fetchall()

            self.logger.info("📋 Últimos repositorios procesados:")
            for repo_name, timestamp in recent_repos:
                self.logger.info(f"  - {repo_name} ({timestamp})")
        else:
            self.logger.info("🆕 MODO INICIAL: Empezando extracción desde cero")

    def run_collection_cycle(self):
        """Ejecuta un ciclo completo de recolección"""
        self.logger.info("Iniciando ciclo de recolección...")

        for filename in TARGET_FILES:
            self.logger.info(f"Buscando repositorios con archivo: {filename}")
            repositories = self.search_repositories_by_file(filename)

            for repo_data in repositories:
                processed_repo = self.process_repository(repo_data)
                if processed_repo:
                    self.save_repository_data(processed_repo)

                time.sleep(self.config.delay_between_requests)

            self.logger.info(f"Procesados {len(repositories)} repos para {filename}")

        self.save_stats()
        self.print_stats()

    def run_continuous(self):
        """Ejecuta recolección continua"""
        self.logger.info("Iniciando recolección continua...")

        # Verificar modo continuación vs inicial
        self.check_resume_capability()

        last_backup = datetime.now()

        try:
            while True:
                self.run_collection_cycle()

                # Crear backup periódico
                if datetime.now() - last_backup > timedelta(hours=self.config.backup_interval_hours):
                    self.create_backup()
                    last_backup = datetime.now()

                self.logger.info(f"Ciclo completado. Esperando {self.config.delay_between_batches}s...")
                time.sleep(self.config.delay_between_batches)

        except KeyboardInterrupt:
            self.logger.info("Detenido por usuario")
        except Exception as e:
            self.logger.error(f"Error inesperado: {e}")
        finally:
            self.save_stats()
            self.create_backup()
            self.db_connection.close()


def main():
    """Función principal"""
    config = Config()

    if not config.github_token:
        print("ERROR: GITHUB_TOKEN no encontrado en variables de entorno")
        sys.exit(1)

    collector = GitHubCollector(config)

    # Verificar tipo de token y límites
    print("🔍 Verificando tipo de token GitHub...")
    token_info = collector.check_token_type_and_limits()
    collector.print_token_info(token_info)

    if "error" not in token_info:
        collector.optimize_delays_for_token(token_info)

    print("\n" + "=" * 50)
    print("GitHub Data Collector iniciado correctamente")
    print("Presiona Ctrl+C para detener...")
    print("=" * 50)

    collector.run_continuous()


if __name__ == "__main__":
    main()