"""
Configuration module for GitHub Repository Scraper
Handles environment variables and application settings
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# GitHub API Configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
if not GITHUB_TOKEN:
    print("⚠️  WARNING: No GITHUB_TOKEN found. API rate limits will be very low.")

# API Configuration
MAX_REPOS_PER_QUERY = int(os.getenv('MAX_REPOS_PER_QUERY', 100))
REQUESTS_PER_SECOND = float(os.getenv('REQUESTS_PER_SECOND', 1.0))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
RETRY_DELAY = float(os.getenv('RETRY_DELAY', 1.0))

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://github_user:github_pass@localhost:5432/github_repos')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = os.getenv('DB_NAME', 'github_repos')
DB_USER = os.getenv('DB_USER', 'github_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'github_pass')

# Phase Control Configuration
RUN_PHASE1 = os.getenv('RUN_PHASE1', 'true').lower() == 'true'
RUN_PHASE2 = os.getenv('RUN_PHASE2', 'true').lower() == 'true'

# Phase 1 Configuration (Fast Basic Collection)
PHASE1_FILE_TYPES = os.getenv('PHASE1_FILE_TYPES', '.env,.config,.yml,.yaml,.json,.xml,.properties,.ini,.conf,.cfg,.toml,.dockerfile,.docker-compose.yml,.gitignore,.editorconfig,.travis.yml,.circleci,.github,.vscode,.idea,requirements.txt,package.json,composer.json,Gemfile,Cargo.toml,go.mod,pom.xml,build.gradle,CMakeLists.txt,Makefile,.eslintrc,.babelrc,.prettierrc,webpack.config.js,tsconfig.json,tailwind.config.js,next.config.js,nuxt.config.js,vue.config.js,angular.json,pubspec.yaml,Podfile,build.sbt,mix.exs,deno.json,.terraform,.ansible,.helm').split(',')
PHASE1_MIN_STARS = int(os.getenv('PHASE1_MIN_STARS', 0))
PHASE1_MAX_REPOS = int(os.getenv('PHASE1_MAX_REPOS', 50000))  # Aumentado a 50K repos
PHASE1_MAX_AGE_YEARS = int(os.getenv('PHASE1_MAX_AGE_YEARS', 3))  # Solo repos de últimos 3 años
PHASE1_EXCLUDE_FORKS = os.getenv('PHASE1_EXCLUDE_FORKS', 'false').lower() == 'true'

# Phase 2 Configuration (Detailed Enrichment)
PHASE2_MIN_STARS = int(os.getenv('PHASE2_MIN_STARS', 10))
PHASE2_MAX_AGE_YEARS = int(os.getenv('PHASE2_MAX_AGE_YEARS', 5))
PHASE2_MAX_REPOS = int(os.getenv('PHASE2_MAX_REPOS', 1000))
PHASE2_SKIP_FORKS = os.getenv('PHASE2_SKIP_FORKS', 'true').lower() == 'true'

# Phase 2 Parallelization Configuration
PHASE2_MAX_WORKERS = int(os.getenv('PHASE2_MAX_WORKERS', 4))  # Number of concurrent threads
PHASE2_BATCH_SIZE = int(os.getenv('PHASE2_BATCH_SIZE', 50))   # Repos per batch

# Search Configuration
SEARCH_LANGUAGES = os.getenv('SEARCH_LANGUAGES', 'Python,JavaScript,TypeScript,Java,C++,C#,Go,Rust,PHP,Ruby,Swift,Kotlin,Scala,R,MATLAB,Perl,Shell,PowerShell,Lua,Dart,Elixir,Haskell,Clojure,F#,Julia,Nim,Crystal,Zig').split(',')
SEARCH_TOPICS = os.getenv('SEARCH_TOPICS', 'api,web,database,security,config,environment,devops,automation,tool,framework,library,cli,microservice,docker,kubernetes,terraform,ansible').split(',')

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# File paths for sensitive data detection
SENSITIVE_KEYWORDS = [
    'password', 'passwd', 'secret', 'key', 'token', 'api_key', 
    'private_key', 'auth', 'credential', 'config', 'env', 'database'
]

CONFIG_FILE_PATTERNS = [
    r'.*\.env$', r'.*\.config$', r'.*config\..*', r'.*\.yml$', r'.*\.yaml$',
    r'.*\.json$', r'.*\.xml$', r'.*\.properties$', r'.*\.ini$', r'.*\.conf$',
    r'.*\.cfg$', r'.*\.toml$'
]

print(f"🔧 Configuration loaded:")
print(f"   - GitHub Token: {'✅ Set' if GITHUB_TOKEN else '❌ Missing'}")
print(f"   - Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
print(f"   - Phase 1: {'✅ Enabled' if RUN_PHASE1 else '❌ Disabled'}")
print(f"   - Phase 2: {'✅ Enabled' if RUN_PHASE2 else '❌ Disabled'}")