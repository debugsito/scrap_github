-- Comprehensive Indexing Strategy for GitHub Repository Scraper
-- Optimized for ML/Data Mining queries and two-phase collection

-- Primary performance indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_github_id 
    ON repositories(github_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_full_name 
    ON repositories(full_name);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_stargazers_count 
    ON repositories(stargazers_count DESC);

-- Phase tracking indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_phase1_completed 
    ON repositories(phase1_completed, phase1_completed_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_phase2_completed 
    ON repositories(phase2_completed, phase2_completed_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_phase2_candidates 
    ON repositories(phase1_completed, phase2_completed, stargazers_count DESC, created_at DESC)
    WHERE phase1_completed = true AND phase2_completed = false;

-- Language and topic analysis indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_language 
    ON repositories(language) WHERE language IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_main_language 
    ON repositories(main_language) WHERE main_language IS NOT NULL;

-- JSONB indexes for complex queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_topics_gin 
    ON repositories USING gin(topics) WHERE topics IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_language_stats_gin 
    ON repositories USING gin(language_stats) WHERE language_stats IS NOT NULL;

-- Timestamp indexes for time-based analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_created_at 
    ON repositories(created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_updated_at 
    ON repositories(updated_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_pushed_at 
    ON repositories(pushed_at DESC);

-- Owner analysis indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_owner_login 
    ON repositories(owner_login);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_owner_type 
    ON repositories(owner_type);

-- Repository characteristics indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_fork_status 
    ON repositories(fork, stargazers_count DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_private_status 
    ON repositories(private, visibility);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_archived_disabled 
    ON repositories(archived, disabled) WHERE archived = false AND disabled = false;

-- Size and activity indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_size 
    ON repositories(size DESC) WHERE size > 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_activity_score 
    ON repositories(activity_score DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_age_days 
    ON repositories(age_days) WHERE age_days IS NOT NULL;

-- License analysis indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_license_key 
    ON repositories(license_key) WHERE license_key IS NOT NULL;

-- Contributor and activity indexes (Phase 2 data)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_contributors_count 
    ON repositories(contributors_count DESC) WHERE contributors_count IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_commits_count 
    ON repositories(commits_count DESC) WHERE commits_count IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_releases_count 
    ON repositories(releases_count DESC) WHERE releases_count IS NOT NULL;

-- File findings indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_found_files_repository_id 
    ON found_files(repository_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_found_files_filename 
    ON found_files(filename);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_found_files_config_files 
    ON found_files(repository_id, is_config_file) WHERE is_config_file = true;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_found_files_secret_files 
    ON found_files(repository_id, is_secret_file) WHERE is_secret_file = true;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_found_files_file_type 
    ON found_files(file_type) WHERE file_type IS NOT NULL;

-- Owner table indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_owners_github_id 
    ON owners(github_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_owners_login 
    ON owners(login);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_owners_type 
    ON owners(type);

-- Processing stats indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_stats_phase 
    ON processing_stats(phase, started_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_stats_completed 
    ON processing_stats(completed_at DESC) WHERE completed_at IS NOT NULL;

-- Composite indexes for complex ML queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_ml_features 
    ON repositories(stargazers_count DESC, forks_count DESC, age_days, language)
    WHERE fork = false AND archived = false AND disabled = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_popular_recent 
    ON repositories(stargazers_count DESC, created_at DESC)
    WHERE stargazers_count >= 10 AND fork = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_active_projects 
    ON repositories(pushed_at DESC, stargazers_count DESC)
    WHERE pushed_at >= CURRENT_DATE - INTERVAL '1 year' AND fork = false;

-- Language-specific indexes for analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_python_projects 
    ON repositories(stargazers_count DESC, created_at DESC)
    WHERE language = 'Python' AND fork = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_javascript_projects 
    ON repositories(stargazers_count DESC, created_at DESC)
    WHERE language = 'JavaScript' AND fork = false;

-- Full-text search index for descriptions
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_description_fts 
    ON repositories USING gin(to_tsvector('english', description))
    WHERE description IS NOT NULL;

-- Partial indexes for specific use cases
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_templates 
    ON repositories(stargazers_count DESC)
    WHERE is_template = true;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_with_pages 
    ON repositories(stargazers_count DESC)
    WHERE has_pages = true;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_repositories_with_releases 
    ON repositories(releases_count DESC, latest_release_tag)
    WHERE releases_count > 0;

-- Materialized view for common aggregations (optional)
-- This can speed up dashboard queries
CREATE MATERIALIZED VIEW IF NOT EXISTS repository_stats AS
SELECT 
    language,
    COUNT(*) as total_repos,
    COUNT(*) FILTER (WHERE fork = false) as non_fork_repos,
    AVG(stargazers_count) as avg_stars,
    MAX(stargazers_count) as max_stars,
    AVG(forks_count) as avg_forks,
    COUNT(*) FILTER (WHERE phase2_completed = true) as enriched_repos,
    AVG(contributors_count) FILTER (WHERE contributors_count IS NOT NULL) as avg_contributors
FROM repositories
WHERE language IS NOT NULL
GROUP BY language
ORDER BY total_repos DESC;

-- Index on materialized view
CREATE INDEX IF NOT EXISTS idx_repository_stats_language 
    ON repository_stats(language);

-- Refresh function for materialized view
CREATE OR REPLACE FUNCTION refresh_repository_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY repository_stats;
END;
$$ LANGUAGE plpgsql;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Comprehensive indexing strategy applied successfully!';
    RAISE NOTICE 'Indexes created: 35+ performance and analytics indexes';
    RAISE NOTICE 'Features: GIN indexes for JSONB, partial indexes, composite indexes';
    RAISE NOTICE 'Materialized view: repository_stats for fast aggregations';
    RAISE NOTICE 'Run: SELECT refresh_repository_stats(); to update stats view';
END $$;