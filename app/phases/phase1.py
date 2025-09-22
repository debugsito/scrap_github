"""
Phase 1: Fast Basic Repository Collection
Efficiently collects basic repository data using GitHub Search API
Now with parallel processing support for improved performance
"""

import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import json

from app.config import (
    GITHUB_TOKEN, MAX_REPOS_PER_QUERY, REQUESTS_PER_SECOND,
    PHASE1_FILE_TYPES, PHASE1_MIN_STARS, PHASE1_MAX_REPOS, PHASE1_MAX_AGE_YEARS, PHASE1_EXCLUDE_FORKS,
    PHASE1_MAX_WORKERS, PHASE1_BATCH_SIZE,
    SEARCH_LANGUAGES, SEARCH_TOPICS
)
from app.models import Repository, db, ensure_connection
from app.utils import make_github_request, print_progress, setup_logging

logger = logging.getLogger(__name__)

class Phase1Collector:
    """Fast basic repository collection using GitHub Search API with parallel processing"""
    
    def __init__(self):
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Repository-Scraper'
        }
        if GITHUB_TOKEN:
            self.headers['Authorization'] = f'token {GITHUB_TOKEN}'
        
        # Thread-safe repository tracking
        self.collected_repos: Set[int] = set()
        self.repo_lock = threading.Lock()
        self.total_collected = 0
        
        # Thread-safe rate limiting
        self.rate_limiter = threading.Semaphore(PHASE1_MAX_WORKERS)
        self.last_request_time = threading.local()
        self.request_lock = threading.Lock()
        
        # Ensure database connection
        if not ensure_connection():
            raise Exception("Cannot connect to database")
    
    def thread_safe_request(self, url: str, params: Dict = None) -> Optional[requests.Response]:
        """Make a thread-safe API request with optimized token rotation"""
        try:
            # Use optimized request function with token manager
            from app.utils import make_github_request_optimized
            return make_github_request_optimized(url, params)
        except Exception as e:
            logger.error(f"Error in thread-safe request: {e}")
            return None
    
    def add_repository_safe(self, repo_id: int, repo_data: Dict) -> bool:
        """Thread-safe method to add repository to collection"""
        with self.repo_lock:
            if repo_id not in self.collected_repos:
                self.collected_repos.add(repo_id)
                return True
            return False
    
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
                
                response = self.thread_safe_request(url, params)
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
                    if repo_id and self.add_repository_safe(repo_id, item):
                        repositories.append(item)
                        
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
                
                response = self.thread_safe_request(url, params)
                if not response:
                    break
                
                data = response.json()
                items = data.get('items', [])
                
                if not items:
                    break
                
                for item in items:
                    repo_id = item.get('id')
                    if repo_id and self.add_repository_safe(repo_id, item):
                        repositories.append(item)
                        
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
    
    def search_worker(self, search_params: Dict) -> List[Dict]:
        """Worker function for parallel searching"""
        search_type = search_params['type']
        
        if search_type == 'file_language':
            file_types = search_params['file_types']
            language = search_params.get('language')
            return self.search_repositories_by_files(file_types, language)
        elif search_type == 'topics':
            topics = search_params['topics']
            return self.search_repositories_by_topics(topics)
        
        return []
    
    def collect_all_basic_repos(self) -> int:
        """Collect all basic repository data in Phase 1 using parallel processing"""
        logger.info(f"🚀 Starting Phase 1: Fast Basic Repository Collection (Parallel Mode)")
        logger.info(f"⚡ Using {PHASE1_MAX_WORKERS} workers with {len(PHASE1_FILE_TYPES)} file types and {len(SEARCH_LANGUAGES)} languages")
        
        start_time = datetime.now()
        self.total_collected = 0
        all_repositories = []
        
        # Prepare search tasks
        search_tasks = []
        
        # Create file type batches for each language
        file_batches = [PHASE1_FILE_TYPES[i:i + PHASE1_BATCH_SIZE] 
                       for i in range(0, len(PHASE1_FILE_TYPES), PHASE1_BATCH_SIZE)]
        
        for language in SEARCH_LANGUAGES:
            for file_batch in file_batches:
                search_tasks.append({
                    'type': 'file_language',
                    'file_types': file_batch,
                    'language': language
                })
        
        # Add topic searches
        topic_batches = [SEARCH_TOPICS[i:i + 3] 
                        for i in range(0, len(SEARCH_TOPICS), 3)]
        
        for topic_batch in topic_batches:
            search_tasks.append({
                'type': 'topics',
                'topics': topic_batch
            })
        
        logger.info(f"📋 Created {len(search_tasks)} search tasks")
        
        # Execute searches in parallel
        completed_tasks = 0
        with ThreadPoolExecutor(max_workers=PHASE1_MAX_WORKERS) as executor:
            # Submit all search tasks
            future_to_task = {
                executor.submit(self.search_worker, task): task
                for task in search_tasks
            }
            
            # Process completed tasks
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    repositories = future.result()
                    all_repositories.extend(repositories)
                    completed_tasks += 1
                    
                    # Update progress
                    print_progress(completed_tasks, len(search_tasks), "Parallel search tasks")
                    
                    # Save in batches to avoid memory issues
                    if len(all_repositories) >= 1000:
                        saved = self.save_repositories_batch(all_repositories)
                        self.total_collected += saved
                        all_repositories = []
                        logger.info(f"💾 Batch saved: {saved} repos (Total: {self.total_collected})")
                    
                except Exception as e:
                    logger.error(f"❌ Search task failed: {e}")
                    completed_tasks += 1
        
        # Save remaining repositories
        if all_repositories:
            saved = self.save_repositories_batch(all_repositories)
            self.total_collected += saved
            logger.info(f"💾 Final batch saved: {saved} repos")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Calculate speedup estimation
        estimated_sequential_time = len(search_tasks) * 30  # ~30 seconds per search task
        speedup = estimated_sequential_time / duration if duration > 0 else 0
        
        logger.info(f"✅ Phase 1 completed in {duration:.1f} seconds")
        logger.info(f"📊 Total repositories collected: {self.total_collected}")
        logger.info(f"⚡ Estimated speedup: {speedup:.1f}x faster than sequential processing")
        logger.info(f"🔍 Unique repositories found: {len(self.collected_repos)}")
        
        return self.total_collected