"""
Token Manager for GitHub API Rate Limit Optimization
Handles multiple tokens with automatic rotation and rate limit detection
"""

import time
import threading
import logging
from typing import List, Dict, Optional
import requests
from datetime import datetime, timedelta

from app.config import GITHUB_TOKENS

logger = logging.getLogger(__name__)

class TokenManager:
    """Manages multiple GitHub tokens for rate limit optimization"""
    
    def __init__(self):
        self.tokens = GITHUB_TOKENS.copy()
        self.current_token_index = 0
        self.token_stats = {}
        self.lock = threading.Lock()
        
        # Initialize token stats
        for i, token in enumerate(self.tokens):
            self.token_stats[i] = {
                'remaining': 5000,
                'reset_time': datetime.now(),
                'last_check': datetime.now(),
                'active': True
            }
        
        logger.info(f"🔑 TokenManager initialized with {len(self.tokens)} tokens")
    
    def get_best_token(self) -> tuple[str, Dict]:
        """Get the token with the most remaining requests"""
        with self.lock:
            if not self.tokens:
                return None, None
            
            # Check rate limits for all tokens
            self._update_token_stats()
            
            # Find token with most remaining requests
            best_index = None
            best_remaining = 0
            
            for i, token in enumerate(self.tokens):
                stats = self.token_stats[i]
                if stats['active'] and stats['remaining'] > best_remaining:
                    best_remaining = stats['remaining']
                    best_index = i
            
            if best_index is None:
                # All tokens exhausted, wait for reset
                self._wait_for_reset()
                return self.get_best_token()
            
            token = self.tokens[best_index]
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'GitHub-Repository-Scraper',
                'Authorization': f'token {token}'
            }
            
            logger.debug(f"Using token {best_index + 1} with {best_remaining} requests remaining")
            return token, headers
    
    def _update_token_stats(self):
        """Update rate limit stats for all tokens"""
        for i, token in enumerate(self.tokens):
            try:
                headers = {
                    'Accept': 'application/vnd.github.v3+json',
                    'User-Agent': 'GitHub-Repository-Scraper',
                    'Authorization': f'token {token}'
                }
                
                response = requests.get('https://api.github.com/rate_limit', 
                                      headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    core_limits = data.get('resources', {}).get('core', {})
                    
                    self.token_stats[i].update({
                        'remaining': core_limits.get('remaining', 0),
                        'reset_time': datetime.fromtimestamp(core_limits.get('reset', 0)),
                        'last_check': datetime.now(),
                        'active': core_limits.get('remaining', 0) > 0
                    })
                    
                    logger.debug(f"Token {i + 1}: {core_limits.get('remaining', 0)} requests remaining")
                
            except Exception as e:
                logger.warning(f"Failed to check rate limit for token {i + 1}: {e}")
                self.token_stats[i]['active'] = False
    
    def _wait_for_reset(self):
        """Wait for the earliest token reset"""
        earliest_reset = min(
            stats['reset_time'] for stats in self.token_stats.values()
        )
        
        wait_time = (earliest_reset - datetime.now()).total_seconds()
        if wait_time > 0:
            logger.info(f"⏳ All tokens exhausted. Waiting {wait_time:.0f} seconds for reset...")
            time.sleep(wait_time + 5)  # Add 5 seconds buffer
            
            # Reactivate all tokens
            for stats in self.token_stats.values():
                stats['active'] = True
    
    def report_stats(self):
        """Report current token usage statistics"""
        total_remaining = sum(stats['remaining'] for stats in self.token_stats.values())
        
        logger.info(f"📊 Token Stats:")
        for i, stats in self.token_stats.items():
            status = "✅" if stats['active'] else "❌"
            logger.info(f"   Token {i + 1}: {stats['remaining']} remaining {status}")
        
        logger.info(f"🚀 Total remaining requests: {total_remaining}")
        return total_remaining

# Global token manager instance
token_manager = TokenManager() if GITHUB_TOKENS else None