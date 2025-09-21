-- GitHub Repository Scraper Database Schema
-- Comprehensive schema to maximize GitHub API field extraction

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Repositories table with maximized field extraction
CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    
    -- Basic GitHub API fields
    github_id BIGINT UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    full_name VARCHAR(500) NOT NULL,
    description TEXT,
    
    -- Repository URLs
    html_url VARCHAR(500),
    clone_url VARCHAR(500),
    git_url VARCHAR(500),
    ssh_url VARCHAR(500),
    
    -- Repository metrics
    size INTEGER,
    stargazers_count INTEGER DEFAULT 0,
    watchers_count INTEGER DEFAULT 0,
    forks_count INTEGER DEFAULT 0,
    open_issues_count INTEGER DEFAULT 0,
    
    -- Language and topics
    language VARCHAR(100),
    topics JSONB,
    
    -- Repository features
    has_issues BOOLEAN DEFAULT false,
    has_projects BOOLEAN DEFAULT false,
    has_wiki BOOLEAN DEFAULT false,
    has_pages BOOLEAN DEFAULT false,
    has_downloads BOOLEAN DEFAULT false,
    
    -- Repository status
    archived BOOLEAN DEFAULT false,
    disabled BOOLEAN DEFAULT false,
    fork BOOLEAN DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    pushed_at TIMESTAMP WITH TIME ZONE,
    
    -- Owner information
    owner_login VARCHAR(255),
    owner_id BIGINT,
    owner_type VARCHAR(50),
    owner_html_url VARCHAR(500),
    owner_avatar_url VARCHAR(500),
    
    -- Branch and license
    default_branch VARCHAR(255),
    license_key VARCHAR(100),
    license_name VARCHAR(255),
    
    -- Privacy and permissions
    visibility VARCHAR(50),
    private BOOLEAN DEFAULT false,
    allow_forking BOOLEAN DEFAULT true,
    is_template BOOLEAN DEFAULT false,
    web_commit_signoff_required BOOLEAN DEFAULT false,
    
    -- Phase 1 tracking
    phase1_completed BOOLEAN DEFAULT false,
    phase1_completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Phase 2 detailed fields
    phase2_completed BOOLEAN DEFAULT false,
    phase2_completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Language analysis (Phase 2)
    main_language VARCHAR(100),
    language_stats JSONB,
    total_code_bytes BIGINT,
    
    -- Contributor analysis (Phase 2)
    contributors_count INTEGER,
    top_contributor VARCHAR(255),
    
    -- Activity metrics (Phase 2)
    commits_count INTEGER,
    branches_count INTEGER,
    releases_count INTEGER,
    latest_release_tag VARCHAR(255),
    
    -- Content analysis (Phase 2)
    readme_content TEXT,
    primary_topic VARCHAR(100),
    
    -- Computed fields for ML analysis (simplified - no generated columns)
    age_days INTEGER,
    days_since_update INTEGER,
    activity_score DECIMAL(10,2),
    
    -- Metadata
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- File findings table (many-to-many relationship)
CREATE TABLE IF NOT EXISTS found_files (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    path VARCHAR(1000),
    file_size BIGINT,
    is_config_file BOOLEAN DEFAULT false,
    is_secret_file BOOLEAN DEFAULT false,
    file_type VARCHAR(50),
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(repository_id, path)
);

-- Repository owners table (normalized)
CREATE TABLE IF NOT EXISTS owners (
    id SERIAL PRIMARY KEY,
    github_id BIGINT UNIQUE NOT NULL,
    login VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(50),
    html_url VARCHAR(500),
    avatar_url VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Processing statistics table
CREATE TABLE IF NOT EXISTS processing_stats (
    id SERIAL PRIMARY KEY,
    phase VARCHAR(20) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    repositories_processed INTEGER DEFAULT 0,
    repositories_successful INTEGER DEFAULT 0,
    repositories_failed INTEGER DEFAULT 0,
    api_requests_made INTEGER DEFAULT 0,
    rate_limit_hits INTEGER DEFAULT 0,
    errors_encountered JSONB,
    processing_notes TEXT
);

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at_utc = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Function to calculate computed fields
CREATE OR REPLACE FUNCTION update_computed_fields()
RETURNS TRIGGER AS $$
BEGIN
    -- Calculate age in days
    IF NEW.created_at IS NOT NULL THEN
        NEW.age_days = EXTRACT(DAYS FROM (CURRENT_TIMESTAMP - NEW.created_at))::INTEGER;
    END IF;
    
    -- Calculate days since update
    IF NEW.updated_at IS NOT NULL THEN
        NEW.days_since_update = EXTRACT(DAYS FROM (CURRENT_TIMESTAMP - NEW.updated_at))::INTEGER;
    END IF;
    
    -- Calculate activity score
    IF NEW.stargazers_count IS NOT NULL AND NEW.forks_count IS NOT NULL THEN
        NEW.activity_score = (NEW.stargazers_count + NEW.forks_count * 2)::DECIMAL(10,2);
    ELSE
        NEW.activity_score = 0;
    END IF;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create update triggers
CREATE TRIGGER update_repositories_updated_at 
    BEFORE UPDATE ON repositories 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_repositories_computed_fields
    BEFORE INSERT OR UPDATE ON repositories
    FOR EACH ROW
    EXECUTE FUNCTION update_computed_fields();

CREATE TRIGGER update_owners_updated_at 
    BEFORE UPDATE ON owners 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE repositories IS 'Main table storing GitHub repository data with maximum field extraction';
COMMENT ON TABLE found_files IS 'Files found in repositories during scanning';
COMMENT ON TABLE owners IS 'Normalized table for repository owners';
COMMENT ON TABLE processing_stats IS 'Statistics and metadata about scraping runs';

COMMENT ON COLUMN repositories.activity_score IS 'Computed score: stars + (forks * 2) for ML ranking';
COMMENT ON COLUMN repositories.age_days IS 'Repository age in days (computed field)';
COMMENT ON COLUMN repositories.language_stats IS 'JSON object with language statistics from GitHub API';
COMMENT ON COLUMN repositories.topics IS 'JSON array of repository topics';

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'GitHub Repository Scraper database schema created successfully!';
    RAISE NOTICE 'Tables: repositories, found_files, owners, processing_stats';
    RAISE NOTICE 'Features: JSONB support, computed fields, full indexing ready';
END $$;