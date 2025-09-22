"""
Phase 1: Fast Basic Repository Collection
Efficiently collects basic repository data using GitHub Search API
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import requests
import json

from app.config import (
    GITHUB_TOKEN, MAX_REPOS_PER_QUERY, REQUESTS_PER_SECOND,
    PHASE1_FILE_TYPES, PHASE1_MIN_STARS, PHASE1_MAX_REPOS, PHASE1_MAX_AGE_YEARS, PHASE1_EXCLUDE_FORKS,
    SEARCH_LANGUAGES, SEARCH_TOPICS
)
from app.models import Repository, db, ensure_connection
from app.utils import make_github_request, print_progress, setup_logging

logger = logging.getLogger(__name__)

class Phase1Collector:
    """Fast basic repository collection using GitHub Search API"""
    
    def __init__(self):
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Repository-Scraper'
        }
        if GITHUB_TOKEN:
            self.headers['Authorization'] = f'token {GITHUB_TOKEN}'
        
        self.collected_repos: Set[int] = set()
        self.total_collected = 0
        
        # Ensure database connection
        if not ensure_connection():
            raise Exception("Cannot connect to database")
    
    def search_repositories_by_files(self, file_types: List[str], 
                                   language: str = None) -> List[Dict]:
        """Search repositories containing specific file types"""
        repositories = []
        
        # Calculate date filter for recent repositories
        cutoff_date = datetime.now() - timedelta(days=PHASE1_MAX_AGE_YEARS * 365)
        date_filter = cutoff_date.strftime('%Y-%m-%d')
        
        for file_type in file_types:
            query_parts = [f'filename:{file_type}']
            
            if language:
                query_parts.append(f'language:{language}')
            
            if PHASE1_MIN_STARS > 0:
                query_parts.append(f'stars:>={PHASE1_MIN_STARS}')
            
            # Add date filter for recent repos
            query_parts.append(f'created:>={date_filter}')
            
            # Exclude forks if configured
            if PHASE1_EXCLUDE_FORKS:
                query_parts.append('fork:false')
            
            query = ' '.join(query_parts)
            
            logger.info(f"🔍 Searching repositories with {file_type} files (language: {language or 'any'}, created after: {date_filter})")
            
            page = 1
            while len(repositories) < PHASE1_MAX_REPOS:
                url = 'https://api.github.com/search/repositories'
                params = {
                    'q': query,
                    'sort': 'updated',  # Sort by most recently updated
                    'order': 'desc',
                    'per_page': min(100, MAX_REPOS_PER_QUERY),
                    'page': page
                }
                
                response = make_github_request(url, self.headers, params)
                if not response:
                    logger.warning(f"No response for query: {query}")
                    break
                
                data = response.json()
                items = data.get('items', [])
                
                if not items:
                    logger.info(f"No more results for {file_type}")
                    break
                
                for item in items:
                    repo_id = item.get('id')
                    if repo_id and repo_id not in self.collected_repos:
                        repositories.append(item)
                        self.collected_repos.add(repo_id)
                        
                        if len(repositories) >= PHASE1_MAX_REPOS:
                            break
                
                print_progress(len(repositories), PHASE1_MAX_REPOS, 
                             f"Collecting {file_type} repos")
                
                page += 1
                time.sleep(1.0 / REQUESTS_PER_SECOND)
                
                # GitHub API limit: max 1000 results per search
                if page > 10:
                    break
        
        return repositories
    
    def search_repositories_by_topics(self, topics: List[str]) -> List[Dict]:
        """Search repositories by topics"""
        repositories = []
        
        # Calculate date filter for recent repositories  
        cutoff_date = datetime.now() - timedelta(days=PHASE1_MAX_AGE_YEARS * 365)
        date_filter = cutoff_date.strftime('%Y-%m-%d')
        
        for topic in topics:
            query_parts = [f'topic:{topic}']
            
            if PHASE1_MIN_STARS > 0:
                query_parts.append(f'stars:>={PHASE1_MIN_STARS}')
            
            # Add date filter for recent repos
            query_parts.append(f'created:>={date_filter}')
            
            # Exclude forks if configured
            if PHASE1_EXCLUDE_FORKS:
                query_parts.append('fork:false')
            
            query = ' '.join(query_parts)
            
            logger.info(f"🏷️  Searching repositories with topic: {topic} (created after: {date_filter})")
            
            page = 1
            while len(repositories) < PHASE1_MAX_REPOS:
                url = 'https://api.github.com/search/repositories'
                params = {
                    'q': query,
                    'sort': 'updated',  # Sort by most recently updated
                    'order': 'desc',
                    'per_page': min(100, MAX_REPOS_PER_QUERY),
                    'page': page
                }
                
                response = make_github_request(url, self.headers, params)
                if not response:
                    break
                
                data = response.json()
                items = data.get('items', [])
                
                if not items:
                    break
                
                for item in items:
                    repo_id = item.get('id')
                    if repo_id and repo_id not in self.collected_repos:
                        repositories.append(item)
                        self.collected_repos.add(repo_id)
                        
                        if len(repositories) >= PHASE1_MAX_REPOS:
                            break
                
                print_progress(len(repositories), PHASE1_MAX_REPOS, 
                             f"Collecting {topic} repos")
                
                page += 1
                time.sleep(1.0 / REQUESTS_PER_SECOND)
                
                if page > 10:
                    break
        
        return repositories
    
    def extract_found_files(self, repo_data: Dict, repo_id: int) -> List[Dict]:
        """Extract file information for found_files table"""
        files = []
        
        # Check if any target files are mentioned in the repository data
        repo_name = repo_data.get('full_name', '')
        
        for file_type in PHASE1_FILE_TYPES:
            # This is a simplified extraction - in a real implementation,
            # you might want to use the Contents API to get actual file lists
            files.append({
                'repository_id': repo_id,
                'filename': file_type,
                'path': f'/{file_type}',
                'is_config_file': True,
                'is_secret_file': 'secret' in file_type.lower() or 'env' in file_type.lower(),
                'detected_at': datetime.now()
            })
        
        return files
    
    def save_repositories_batch(self, repositories: List[Dict]) -> int:
        """Save a batch of repositories to database"""
        if not repositories:
            return 0
        
        # Convert GitHub API data to Repository objects
        repo_objects = []
        for repo_data in repositories:
            try:
                repo = Repository(repo_data)
                repo_dict = repo.extract_all_basic_fields()
                repo_objects.append(repo_dict)
            except Exception as e:
                logger.error(f"Error processing repository {repo_data.get('full_name')}: {e}")
        
        if not repo_objects:
            return 0
        
        # Bulk insert repositories
        try:
            saved_count = db.bulk_insert_repositories(repo_objects)
            logger.info(f"✅ Saved {saved_count} repositories to database")
            return saved_count
        except Exception as e:
            logger.error(f"❌ Error saving repositories: {e}")
            return 0
    
    def collect_all_basic_repos(self) -> int:
        """Collect all basic repository data in Phase 1"""
        logger.info("🚀 Starting Phase 1: Fast Basic Repository Collection")
        
        start_time = datetime.now()
        all_repositories = []
        
        # Search by file types for each language
        for language in SEARCH_LANGUAGES:
            logger.info(f"🔍 Searching {language} repositories...")
            repos = self.search_repositories_by_files(PHASE1_FILE_TYPES, language)
            all_repositories.extend(repos)
            
            # Save in batches to avoid memory issues
            if len(all_repositories) >= 1000:
                saved = self.save_repositories_batch(all_repositories)
                self.total_collected += saved
                all_repositories = []
        
        # Search by topics
        logger.info("🏷️  Searching by topics...")
        topic_repos = self.search_repositories_by_topics(SEARCH_TOPICS)
        all_repositories.extend(topic_repos)
        
        # Save remaining repositories
        if all_repositories:
            saved = self.save_repositories_batch(all_repositories)
            self.total_collected += saved
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"✅ Phase 1 completed in {duration:.1f} seconds")
        logger.info(f"📊 Total repositories collected: {self.total_collected}")
        
        return self.total_collected