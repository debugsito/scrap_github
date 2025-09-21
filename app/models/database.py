"""
Database management for GitHub Repository Scraper
Handles PostgreSQL connections and operations
"""

import psycopg2
import psycopg2.extras
import logging
from contextlib import contextmanager
from typing import Dict, List, Optional, Any

from app.config import DATABASE_URL, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages PostgreSQL database connections and operations"""
    
    def __init__(self):
        self.connection_params = {
            'host': DB_HOST,
            'port': DB_PORT,
            'database': DB_NAME,
            'user': DB_USER,
            'password': DB_PASSWORD
        }
        self._connection = None
    
    def connect(self) -> bool:
        """Establish database connection"""
        try:
            self._connection = psycopg2.connect(**self.connection_params)
            self._connection.autocommit = True
            logger.info("✅ Database connection established")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
    
    @contextmanager
    def get_cursor(self):
        """Get database cursor with automatic cleanup"""
        if not self._connection:
            if not self.connect():
                raise Exception("Cannot establish database connection")
        
        cursor = self._connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cursor
        finally:
            cursor.close()
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a SELECT query and return results"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Update execution failed: {e}")
            raise
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute multiple queries with different parameters"""
        try:
            with self.get_cursor() as cursor:
                cursor.executemany(query, params_list)
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            raise
    
    def bulk_insert_repositories(self, repositories: List[Dict]) -> int:
        """Efficiently insert multiple repositories"""
        if not repositories:
            return 0
        
        insert_query = """
            INSERT INTO repositories (
                github_id, name, full_name, description, html_url, clone_url, git_url, ssh_url,
                size, stargazers_count, watchers_count, forks_count, open_issues_count,
                language, topics, has_issues, has_projects, has_wiki, has_pages,
                has_downloads, archived, disabled, fork, created_at, updated_at, pushed_at,
                owner_login, owner_id, owner_type, owner_html_url, owner_avatar_url,
                default_branch, license_key, license_name, visibility, private,
                allow_forking, is_template, web_commit_signoff_required,
                phase1_completed, phase1_completed_at
            ) VALUES %s
            ON CONFLICT (github_id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                size = EXCLUDED.size,
                stargazers_count = EXCLUDED.stargazers_count,
                watchers_count = EXCLUDED.watchers_count,
                forks_count = EXCLUDED.forks_count,
                open_issues_count = EXCLUDED.open_issues_count,
                language = EXCLUDED.language,
                topics = EXCLUDED.topics,
                updated_at = EXCLUDED.updated_at,
                pushed_at = EXCLUDED.pushed_at,
                phase1_completed = EXCLUDED.phase1_completed,
                phase1_completed_at = EXCLUDED.phase1_completed_at
        """
        
        # Convert repositories to tuples for bulk insert
        values = []
        for repo in repositories:
            values.append((
                repo.get('github_id'), repo.get('name'), repo.get('full_name'),
                repo.get('description'), repo.get('html_url'), repo.get('clone_url'),
                repo.get('git_url'), repo.get('ssh_url'), repo.get('size'),
                repo.get('stargazers_count'), repo.get('watchers_count'),
                repo.get('forks_count'), repo.get('open_issues_count'),
                repo.get('language'), repo.get('topics'), repo.get('has_issues'),
                repo.get('has_projects'), repo.get('has_wiki'), repo.get('has_pages'),
                repo.get('has_downloads'), repo.get('archived'), repo.get('disabled'),
                repo.get('fork'), repo.get('created_at'), repo.get('updated_at'),
                repo.get('pushed_at'), repo.get('owner_login'), repo.get('owner_id'),
                repo.get('owner_type'), repo.get('owner_html_url'), repo.get('owner_avatar_url'),
                repo.get('default_branch'), repo.get('license_key'), repo.get('license_name'),
                repo.get('visibility'), repo.get('private'), repo.get('allow_forking'),
                repo.get('is_template'), repo.get('web_commit_signoff_required'),
                repo.get('phase1_completed'), repo.get('phase1_completed_at')
            ))
        
        try:
            with self.get_cursor() as cursor:
                psycopg2.extras.execute_values(
                    cursor, insert_query, values,
                    template=None, page_size=100
                )
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Bulk repository insert failed: {e}")
            raise

# Global database manager instance
db = DatabaseManager()

def ensure_connection() -> bool:
    """Ensure database connection is established"""
    if not db._connection:
        return db.connect()
    return True