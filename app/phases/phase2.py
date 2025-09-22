"""
Phase 2: Detailed Repository Enrichment
Intelligently enriches high-value repositories with detailed information
Now with parallel processing support for improved performance
"""

import time
import logging
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

from app.config import (
    GITHUB_TOKEN, REQUESTS_PER_SECOND,
    PHASE2_MIN_STARS, PHASE2_MAX_AGE_YEARS, PHASE2_MAX_REPOS, PHASE2_SKIP_FORKS,
    PHASE2_MAX_WORKERS, PHASE2_BATCH_SIZE
)
from app.models import db, ensure_connection
from app.utils import make_github_request, print_progress

logger = logging.getLogger(__name__)

class Phase2Enricher:
    """Intelligent detailed enrichment for high-value repositories with parallel processing"""
    
    def __init__(self):
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Repository-Scraper'
        }
        if GITHUB_TOKEN:
            self.headers['Authorization'] = f'token {GITHUB_TOKEN}'
        
        self.enriched_count = 0
        self.failed_count = 0
        
        # Thread-safe rate limiting
        self.rate_limiter = threading.Semaphore(PHASE2_MAX_WORKERS)
        self.last_request_time = threading.local()
        self.request_lock = threading.Lock()
        
        # Ensure database connection
        if not ensure_connection():
            raise Exception("Cannot connect to database")
    
    def thread_safe_request(self, url: str) -> Optional[requests.Response]:
        """Make a thread-safe API request with optimized token rotation"""
        try:
            # Use optimized request function with token manager
            from app.utils import make_github_request_optimized
            return make_github_request_optimized(url)
        except Exception as e:
            logger.error(f"Error in thread-safe request: {e}")
            return None
    
    def get_repositories_for_enrichment(self) -> List[Dict]:
        """Get repositories that need Phase 2 enrichment"""
        
        # Calculate cutoff date for recent repositories
        cutoff_date = datetime.now() - timedelta(days=PHASE2_MAX_AGE_YEARS * 365)
        
        query = """
            SELECT github_id, full_name, stargazers_count, language, fork, created_at
            FROM repositories 
            WHERE phase1_completed = true 
            AND phase2_completed = false
            AND stargazers_count >= %s
            AND created_at >= %s
        """
        params = [PHASE2_MIN_STARS, cutoff_date]
        
        if PHASE2_SKIP_FORKS:
            query += " AND fork = false"
        
        query += """
            ORDER BY stargazers_count DESC, created_at DESC
            LIMIT %s
        """
        params.append(PHASE2_MAX_REPOS)
        
        try:
            repositories = db.execute_query(query, tuple(params))
            logger.info(f"📋 Found {len(repositories)} repositories for Phase 2 enrichment")
            return repositories
        except Exception as e:
            logger.error(f"❌ Error fetching repositories for enrichment: {e}")
            return []
    
    def get_repository_languages(self, full_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed language statistics for repository"""
        url = f'https://api.github.com/repos/{full_name}/languages'
        
        response = self.thread_safe_request(url)
        if not response:
            return None
        
        try:
            languages = response.json()
            if not languages:
                return None
            
            # Calculate total bytes and main language
            total_bytes = sum(languages.values())
            main_language = max(languages.items(), key=lambda x: x[1])[0]
            
            # Calculate percentages
            language_stats = {}
            for lang, bytes_count in languages.items():
                percentage = (bytes_count / total_bytes) * 100
                language_stats[lang] = {
                    'bytes': bytes_count,
                    'percentage': round(percentage, 2)
                }
            
            return {
                'main_language': main_language,
                'language_stats': language_stats,
                'total_code_bytes': total_bytes
            }
        
        except Exception as e:
            logger.error(f"Error processing languages for {full_name}: {e}")
            return None
    
    def get_repository_contributors(self, full_name: str) -> Optional[Dict[str, Any]]:
        """Get contributor information for repository"""
        url = f'https://api.github.com/repos/{full_name}/contributors'
        
        response = self.thread_safe_request(url)
        if not response:
            return None
        
        try:
            contributors = response.json()
            if not contributors or not isinstance(contributors, list):
                return None
            
            contributors_count = len(contributors)
            top_contributor = contributors[0].get('login') if contributors else None
            
            return {
                'contributors_count': contributors_count,
                'top_contributor': top_contributor
            }
        
        except Exception as e:
            logger.error(f"Error processing contributors for {full_name}: {e}")
            return None
    
    def get_repository_activity(self, full_name: str) -> Optional[Dict[str, Any]]:
        """Get repository activity metrics"""
        activity_data = {}
        
        # Get commit count (approximate from commits API)
        commits_url = f'https://api.github.com/repos/{full_name}/commits'
        commits_response = self.thread_safe_request(commits_url + '?per_page=1')
        
        if commits_response:
            # GitHub provides commit count in Link header for pagination
            link_header = commits_response.headers.get('Link', '')
            if 'rel="last"' in link_header:
                try:
                    # Extract page number from last page link
                    last_page = link_header.split('page=')[-1].split('&')[0].split('>')[0]
                    activity_data['commits_count'] = int(last_page)
                except:
                    activity_data['commits_count'] = None
            else:
                # If no pagination, count actual commits returned
                try:
                    commits = commits_response.json()
                    activity_data['commits_count'] = len(commits) if isinstance(commits, list) else None
                except:
                    activity_data['commits_count'] = None
        
        # Get branches count
        branches_url = f'https://api.github.com/repos/{full_name}/branches'
        branches_response = self.thread_safe_request(branches_url)
        
        if branches_response:
            try:
                branches = branches_response.json()
                activity_data['branches_count'] = len(branches) if isinstance(branches, list) else None
            except:
                activity_data['branches_count'] = None
        
        # Get releases count and latest release
        releases_url = f'https://api.github.com/repos/{full_name}/releases'
        releases_response = self.thread_safe_request(releases_url)
        
        if releases_response:
            try:
                releases = releases_response.json()
                if isinstance(releases, list):
                    activity_data['releases_count'] = len(releases)
                    activity_data['latest_release_tag'] = releases[0].get('tag_name') if releases else None
                else:
                    activity_data['releases_count'] = None
                    activity_data['latest_release_tag'] = None
            except:
                activity_data['releases_count'] = None
                activity_data['latest_release_tag'] = None
        
        return activity_data if activity_data else None
    
    def get_repository_readme(self, full_name: str) -> Optional[str]:
        """Get repository README content (first 1000 characters)"""
        url = f'https://api.github.com/repos/{full_name}/readme'
        
        response = self.thread_safe_request(url)
        if not response:
            return None
        
        try:
            readme_data = response.json()
            content = readme_data.get('content', '')
            
            # Decode base64 content
            import base64
            decoded_content = base64.b64decode(content).decode('utf-8', errors='ignore')
            
            # Return first 1000 characters
            return decoded_content[:1000] if decoded_content else None
        
        except Exception as e:
            logger.error(f"Error processing README for {full_name}: {e}")
            return None
    
    def enrich_repository(self, repo_info: Dict) -> bool:
        """Enrich a single repository with detailed information"""
        full_name = repo_info['full_name']
        github_id = repo_info['github_id']
        
        logger.info(f"🔬 Enriching repository: {full_name}")
        
        enrichment_data = {
            'github_id': github_id,
            'phase2_completed': True,
            'phase2_completed_at': datetime.now()
        }
        
        # Get language statistics
        language_data = self.get_repository_languages(full_name)
        if language_data:
            enrichment_data.update(language_data)
        
        time.sleep(1.0 / REQUESTS_PER_SECOND)
        
        # Get contributor information
        contributor_data = self.get_repository_contributors(full_name)
        if contributor_data:
            enrichment_data.update(contributor_data)
        
        time.sleep(1.0 / REQUESTS_PER_SECOND)
        
        # Get activity metrics
        activity_data = self.get_repository_activity(full_name)
        if activity_data:
            enrichment_data.update(activity_data)
        
        time.sleep(1.0 / REQUESTS_PER_SECOND)
        
        # Get README content
        readme_content = self.get_repository_readme(full_name)
        if readme_content:
            enrichment_data['readme_content'] = readme_content
        
        # Update repository in database
        try:
            update_fields = []
            update_params = []
            
            for field, value in enrichment_data.items():
                if field != 'github_id':
                    if field == 'language_stats' and isinstance(value, dict):
                        update_fields.append(f"{field} = %s")
                        update_params.append(json.dumps(value))
                    else:
                        update_fields.append(f"{field} = %s")
                        update_params.append(value)
            
            update_params.append(github_id)
            
            update_query = f"""
                UPDATE repositories 
                SET {', '.join(update_fields)}
                WHERE github_id = %s
            """
            
            rows_updated = db.execute_update(update_query, tuple(update_params))
            
            if rows_updated > 0:
                logger.info(f"✅ Successfully enriched {full_name}")
                return True
            else:
                logger.warning(f"⚠️  No rows updated for {full_name}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error updating repository {full_name}: {e}")
            return False
    
    def enrich_repository_worker(self, repo_info: Dict) -> tuple[bool, str]:
        """Worker function to enrich a single repository (thread-safe)"""
        full_name = repo_info.get('full_name', 'unknown')
        github_id = repo_info.get('github_id')
        
        try:
            logger.debug(f"🔬 Enriching repository: {full_name}")
            
            enrichment_data = {'github_id': github_id}
            
            # Get language statistics
            language_data = self.get_repository_languages(full_name)
            if language_data:
                enrichment_data.update(language_data)
            
            # Get contributor information
            contributor_data = self.get_repository_contributors(full_name)
            if contributor_data:
                enrichment_data.update(contributor_data)
            
            # Get activity metrics
            activity_data = self.get_repository_activity(full_name)
            if activity_data:
                enrichment_data.update(activity_data)
            
            # Get README content
            readme_content = self.get_repository_readme(full_name)
            if readme_content:
                enrichment_data['readme_content'] = readme_content
            
            # Update repository in database
            update_fields = []
            update_params = []
            
            for field, value in enrichment_data.items():
                if field != 'github_id':
                    if field == 'language_stats' and isinstance(value, dict):
                        update_fields.append(f"{field} = %s")
                        update_params.append(json.dumps(value))
                    else:
                        update_fields.append(f"{field} = %s")
                        update_params.append(value)
            
            # Add phase2 completion markers
            update_fields.extend(['phase2_completed = %s', 'phase2_completed_at = %s'])
            update_params.extend([True, datetime.now()])
            update_params.append(github_id)
            
            update_query = f"""
                UPDATE repositories 
                SET {', '.join(update_fields)}
                WHERE github_id = %s
            """
            
            rows_updated = db.execute_update(update_query, tuple(update_params))
            
            if rows_updated > 0:
                logger.info(f"✅ Successfully enriched {full_name}")
                return True, full_name
            else:
                logger.warning(f"⚠️  No rows updated for {full_name}")
                return False, full_name
        
        except Exception as e:
            logger.error(f"❌ Error enriching repository {full_name}: {e}")
            return False, full_name
    
    def enrich_repositories(self) -> int:
        """Enrich all eligible repositories with detailed information using parallel processing"""
        logger.info(f"🔬 Starting Phase 2: Detailed Repository Enrichment (Parallel Mode)")
        logger.info(f"⚡ Using {PHASE2_MAX_WORKERS} workers with batches of {PHASE2_BATCH_SIZE}")
        
        start_time = datetime.now()
        
        # Get repositories for enrichment
        repositories = self.get_repositories_for_enrichment()
        if not repositories:
            logger.info("📭 No repositories found for Phase 2 enrichment")
            return 0
        
        total_repos = len(repositories)
        logger.info(f"📊 Processing {total_repos} repositories for detailed enrichment")
        
        # Process repositories in parallel using ThreadPoolExecutor
        completed_count = 0
        failed_count = 0
        
        with ThreadPoolExecutor(max_workers=PHASE2_MAX_WORKERS) as executor:
            # Submit all tasks
            future_to_repo = {
                executor.submit(self.enrich_repository_worker, repo): repo
                for repo in repositories
            }
            
            # Process completed tasks
            for future in as_completed(future_to_repo):
                repo = future_to_repo[future]
                try:
                    success, repo_name = future.result()
                    if success:
                        completed_count += 1
                    else:
                        failed_count += 1
                    
                    # Update progress
                    total_processed = completed_count + failed_count
                    print_progress(total_processed, total_repos, "Enriching repositories")
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Task failed for {repo.get('full_name', 'unknown')}: {e}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"✅ Phase 2 completed in {duration:.1f} seconds")
        logger.info(f"📊 Total repositories processed: {completed_count + failed_count}/{total_repos}")
        logger.info(f"✅ Successfully enriched: {completed_count}")
        logger.info(f"❌ Failed: {failed_count}")
        
        # Calculate speedup
        estimated_sequential_time = total_repos * 8  # ~8 seconds per repo sequentially
        speedup = estimated_sequential_time / duration if duration > 0 else 0
        logger.info(f"⚡ Estimated speedup: {speedup:.1f}x faster than sequential processing")
        
        self.enriched_count = completed_count
        self.failed_count = failed_count
        
        return completed_count