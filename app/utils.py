"""
Utility functions for GitHub Repository Scraper
"""

import time
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

def setup_logging(log_file: str = "github_collector.log") -> logging.Logger:
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def rate_limit_handler(response: requests.Response) -> None:
    """Handle GitHub API rate limiting"""
    if response.status_code == 403:
        # Check if it's a rate limit issue
        remaining = response.headers.get('X-RateLimit-Remaining', '0')
        if remaining == '0':
            reset_time = int(response.headers.get('X-RateLimit-Reset', time.time()))
            sleep_time = max(reset_time - time.time(), 60)
            print(f"⏰ Rate limit reached. Sleeping for {sleep_time:.0f} seconds...")
            time.sleep(sleep_time)

def make_github_request(url: str, headers: Dict[str, str], 
                       params: Optional[Dict[str, Any]] = None,
                       max_retries: int = 3) -> Optional[requests.Response]:
    """Make a request to GitHub API with retry logic and rate limiting"""
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                rate_limit_handler(response)
                continue
            elif response.status_code == 404:
                print(f"⚠️  Resource not found: {url}")
                return None
            else:
                print(f"❌ Request failed with status {response.status_code}: {response.text}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request exception: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
    
    return None

def calculate_repository_age_days(created_at: datetime) -> int:
    """Calculate repository age in days"""
    if not created_at:
        return 0
    return (datetime.now() - created_at.replace(tzinfo=None)).days

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def is_repository_active(pushed_at: datetime, days_threshold: int = 365) -> bool:
    """Check if repository has been active within threshold days"""
    if not pushed_at:
        return False
    days_since_push = (datetime.now() - pushed_at.replace(tzinfo=None)).days
    return days_since_push <= days_threshold

def extract_owner_from_full_name(full_name: str) -> str:
    """Extract owner name from repository full name"""
    return full_name.split('/')[0] if '/' in full_name else ''

def extract_repo_name_from_full_name(full_name: str) -> str:
    """Extract repository name from full name"""
    return full_name.split('/')[-1] if '/' in full_name else full_name

def sanitize_description(description: Optional[str]) -> Optional[str]:
    """Sanitize repository description for database storage"""
    if not description:
        return None
    # Remove excessive whitespace and limit length
    sanitized = ' '.join(description.split())
    return sanitized[:500] if len(sanitized) > 500 else sanitized

def parse_github_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Parse GitHub API datetime string"""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None

def build_search_query(file_types: list, languages: list = None, 
                      min_stars: int = 0, max_results: int = 1000) -> str:
    """Build GitHub search query string"""
    query_parts = []
    
    # Add file type searches
    if file_types:
        file_queries = [f'filename:{ft}' for ft in file_types]
        query_parts.append(f"({' OR '.join(file_queries)})")
    
    # Add language filter
    if languages:
        lang_queries = [f'language:{lang}' for lang in languages]
        query_parts.append(f"({' OR '.join(lang_queries)})")
    
    # Add minimum stars
    if min_stars > 0:
        query_parts.append(f'stars:>={min_stars}')
    
    return ' '.join(query_parts)

def print_progress(current: int, total: int, prefix: str = "Progress") -> None:
    """Print progress bar"""
    percent = (current / total) * 100 if total > 0 else 0
    bar_length = 50
    filled_length = int(bar_length * current // total) if total > 0 else 0
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    print(f'\r{prefix}: |{bar}| {percent:.1f}% ({current}/{total})', end='', flush=True)
    if current == total:
        print()  # New line when complete