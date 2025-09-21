"""
Repository data model with maximum field extraction from GitHub API
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any


class Repository:
    """Repository model that maximizes field extraction from GitHub API responses"""
    
    def __init__(self, api_data: Dict[str, Any]):
        """Initialize repository from GitHub API response"""
        self.raw_data = api_data
        
        # Basic repository information
        self.github_id = api_data.get('id')
        self.name = api_data.get('name')
        self.full_name = api_data.get('full_name')
        self.description = api_data.get('description')
        
        # URLs
        self.html_url = api_data.get('html_url')
        self.clone_url = api_data.get('clone_url')
        self.git_url = api_data.get('git_url')
        self.ssh_url = api_data.get('ssh_url')
        self.svn_url = api_data.get('svn_url')
        
        # Repository metrics
        self.size = api_data.get('size')
        self.stargazers_count = api_data.get('stargazers_count')
        self.watchers_count = api_data.get('watchers_count')
        self.forks_count = api_data.get('forks_count')
        self.open_issues_count = api_data.get('open_issues_count')
        
        # Language and topics
        self.language = api_data.get('language')
        self.topics = api_data.get('topics', [])
        
        # Repository features
        self.has_issues = api_data.get('has_issues')
        self.has_projects = api_data.get('has_projects')
        self.has_wiki = api_data.get('has_wiki')
        self.has_pages = api_data.get('has_pages')
        self.has_downloads = api_data.get('has_downloads')
        
        # Repository status
        self.archived = api_data.get('archived')
        self.disabled = api_data.get('disabled')
        self.fork = api_data.get('fork')
        
        # Timestamps
        self.created_at = self._parse_datetime(api_data.get('created_at'))
        self.updated_at = self._parse_datetime(api_data.get('updated_at'))
        self.pushed_at = self._parse_datetime(api_data.get('pushed_at'))
        
        # Owner information
        owner = api_data.get('owner', {})
        self.owner_login = owner.get('login')
        self.owner_id = owner.get('id')
        self.owner_type = owner.get('type')
        self.owner_html_url = owner.get('html_url')
        self.owner_avatar_url = owner.get('avatar_url')
        
        # Branch and license
        self.default_branch = api_data.get('default_branch')
        license_info = api_data.get('license', {})
        self.license_key = license_info.get('key') if license_info else None
        self.license_name = license_info.get('name') if license_info else None
        
        # Privacy and permissions
        self.visibility = api_data.get('visibility')
        self.private = api_data.get('private')
        self.allow_forking = api_data.get('allow_forking')
        self.is_template = api_data.get('is_template')
        self.web_commit_signoff_required = api_data.get('web_commit_signoff_required')
        
        # Phase tracking
        self.phase1_completed = False
        self.phase1_completed_at = None
        self.phase2_completed = False
        self.phase2_completed_at = None
        
        # Phase 2 fields (detailed enrichment)
        self.main_language = None
        self.language_stats = None
        self.total_code_bytes = None
        self.contributors_count = None
        self.top_contributor = None
        self.commits_count = None
        self.branches_count = None
        self.releases_count = None
        self.latest_release_tag = None
        self.readme_content = None
        self.primary_topic = None
    
    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string to datetime object"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None
    
    def extract_all_basic_fields(self) -> Dict[str, Any]:
        """Extract all available basic fields from GitHub API for Phase 1"""
        return {
            'github_id': self.github_id,
            'name': self.name,
            'full_name': self.full_name,
            'description': self.description,
            'html_url': self.html_url,
            'clone_url': self.clone_url,
            'git_url': self.git_url,
            'ssh_url': self.ssh_url,
            'size': self.size,
            'stargazers_count': self.stargazers_count,
            'watchers_count': self.watchers_count,
            'forks_count': self.forks_count,
            'open_issues_count': self.open_issues_count,
            'language': self.language,
            'topics': json.dumps(self.topics) if self.topics else None,
            'has_issues': self.has_issues,
            'has_projects': self.has_projects,
            'has_wiki': self.has_wiki,
            'has_pages': self.has_pages,
            'has_downloads': self.has_downloads,
            'archived': self.archived,
            'disabled': self.disabled,
            'fork': self.fork,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'pushed_at': self.pushed_at,
            'owner_login': self.owner_login,
            'owner_id': self.owner_id,
            'owner_type': self.owner_type,
            'owner_html_url': self.owner_html_url,
            'owner_avatar_url': self.owner_avatar_url,
            'default_branch': self.default_branch,
            'license_key': self.license_key,
            'license_name': self.license_name,
            'visibility': self.visibility,
            'private': self.private,
            'allow_forking': self.allow_forking,
            'is_template': self.is_template,
            'web_commit_signoff_required': self.web_commit_signoff_required,
            'phase1_completed': True,
            'phase1_completed_at': datetime.now()
        }
    
    def extract_detailed_fields(self) -> Dict[str, Any]:
        """Extract detailed fields for Phase 2 enrichment"""
        return {
            'main_language': self.main_language,
            'language_stats': json.dumps(self.language_stats) if self.language_stats else None,
            'total_code_bytes': self.total_code_bytes,
            'contributors_count': self.contributors_count,
            'top_contributor': self.top_contributor,
            'commits_count': self.commits_count,
            'branches_count': self.branches_count,
            'releases_count': self.releases_count,
            'latest_release_tag': self.latest_release_tag,
            'readme_content': self.readme_content,
            'primary_topic': self.primary_topic,
            'phase2_completed': True,
            'phase2_completed_at': datetime.now()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert repository to dictionary for JSON serialization"""
        basic_fields = self.extract_all_basic_fields()
        detailed_fields = self.extract_detailed_fields()
        
        # Merge both field sets
        result = {**basic_fields, **detailed_fields}
        
        # Convert datetime objects to ISO strings for JSON serialization
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
        
        return result
    
    def __repr__(self) -> str:
        return f"Repository(id={self.github_id}, name='{self.full_name}', stars={self.stargazers_count})"