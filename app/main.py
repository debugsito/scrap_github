#!/usr/bin/env python3
"""
GitHub Repository Scraper - Two-Phase Architecture
Fast basic collection + intelligent detailed enrichment

Usage:
    python -m app.main                    # Run both phases
    python -m app.main --phase1-only      # Only basic collection
    python -m app.main --phase2-only      # Only detailed enrichment
    python -m app.main --stats            # Show database statistics
"""

import sys
import argparse
import logging
from datetime import datetime

if __package__ is None:
    print("\n[ERROR] Run this script with:\n    python3 -m app.main\nFrom the project root for imports to work.\n")
    sys.exit(1)

from app.config import RUN_PHASE1, RUN_PHASE2, LOG_LEVEL
from app.phases import Phase1Collector, Phase2Enricher
from app.models import db, ensure_connection
from app.utils import setup_logging

def show_database_stats():
    """Show current database statistics"""
    if not ensure_connection():
        print("❌ Cannot connect to database")
        return
    
    try:
        # Repository counts
        repo_stats = db.execute_query("""
            SELECT 
                COUNT(*) as total_repos,
                COUNT(*) FILTER (WHERE phase1_completed = true) as phase1_completed,
                COUNT(*) FILTER (WHERE phase2_completed = true) as phase2_completed,
                COUNT(*) FILTER (WHERE fork = false) as non_forks,
                AVG(stargazers_count) as avg_stars,
                MAX(stargazers_count) as max_stars,
                COUNT(DISTINCT language) as unique_languages,
                COUNT(DISTINCT owner_login) as unique_owners
            FROM repositories
        """)[0]
        
        # File stats
        file_stats = db.execute_query("""
            SELECT 
                COUNT(*) as total_files,
                COUNT(DISTINCT filename) as unique_filenames,
                COUNT(*) FILTER (WHERE is_config_file = true) as config_files,
                COUNT(*) FILTER (WHERE is_secret_file = true) as secret_files
            FROM found_files
        """)[0]
        
        # Top languages
        top_languages = db.execute_query("""
            SELECT language, COUNT(*) as count 
            FROM repositories 
            WHERE language IS NOT NULL 
            GROUP BY language 
            ORDER BY count DESC 
            LIMIT 10
        """)
        
        print("\n📊 DATABASE STATISTICS")
        print("=" * 50)
        print(f"Total Repositories: {repo_stats['total_repos']:,}")
        print(f"Phase 1 Completed: {repo_stats['phase1_completed']:,}")
        print(f"Phase 2 Completed: {repo_stats['phase2_completed']:,}")
        print(f"Non-fork Repos: {repo_stats['non_forks']:,}")
        avg_stars = repo_stats['avg_stars'] or 0
        max_stars = repo_stats['max_stars'] or 0
        print(f"Average Stars: {avg_stars:.1f}")
        print(f"Max Stars: {max_stars:,}")
        print(f"Unique Languages: {repo_stats['unique_languages']}")
        print(f"Unique Owners: {repo_stats['unique_owners']}")
        
        print(f"\nTotal Files Found: {file_stats['total_files']:,}")
        print(f"Unique Filenames: {file_stats['unique_filenames']}")
        print(f"Config Files: {file_stats['config_files']:,}")
        print(f"Potential Secret Files: {file_stats['secret_files']:,}")
        
        if top_languages:
            print(f"\n🔥 TOP LANGUAGES:")
            for i, lang in enumerate(top_languages, 1):
                print(f"{i:2d}. {lang['language']:<15} ({lang['count']:,} repos)")
        else:
            print(f"\n🔥 TOP LANGUAGES: No data yet")
        
        print("\n" + "=" * 50)
        
    except Exception as e:
        print(f"❌ Error getting statistics: {e}")

def run_phase1_only():
    """Run only Phase 1: Basic repository collection"""
    logger = setup_logging("github_collector_phase1.log")
    logger.info("🚀 Starting Phase 1 ONLY mode")
    
    collector = Phase1Collector()
    repos_collected = collector.collect_all_basic_repos()
    
    logger.info(f"✅ Phase 1 completed: {repos_collected} repositories collected")
    print(f"\n🎉 Phase 1 completed successfully!")
    print(f"📊 Collected {repos_collected} repositories")
    print(f"💾 Data saved to PostgreSQL database")
    print(f"🔍 Run 'python -m app.main --stats' to see statistics")

def run_phase2_only():
    """Run only Phase 2: Detailed enrichment"""
    logger = setup_logging("github_collector_phase2.log")
    logger.info("🔬 Starting Phase 2 ONLY mode")
    
    enricher = Phase2Enricher()
    repos_enriched = enricher.enrich_repositories()
    
    logger.info(f"✅ Phase 2 completed: {repos_enriched} repositories enriched")
    print(f"\n🎉 Phase 2 completed successfully!")
    print(f"📊 Enriched {repos_enriched} repositories")
    print(f"💾 Data updated in PostgreSQL database")

def run_both_phases():
    """Run both phases in sequence"""
    logger = setup_logging("github_collector_full.log")
    logger.info("🚀 Starting FULL mode (both phases)")
    
    total_collected = 0
    total_enriched = 0
    
    if RUN_PHASE1:
        logger.info("Starting Phase 1...")
        collector = Phase1Collector()
        total_collected = collector.collect_all_basic_repos()
        logger.info(f"Phase 1 completed: {total_collected} repositories")
    
    if RUN_PHASE2:
        logger.info("Starting Phase 2...")
        enricher = Phase2Enricher()
        total_enriched = enricher.enrich_repositories()
        logger.info(f"Phase 2 completed: {total_enriched} repositories")
    
    print(f"\n🎉 Full collection completed successfully!")
    if total_collected > 0:
        print(f"📊 Phase 1: {total_collected} repositories collected")
    if total_enriched > 0:
        print(f"🔬 Phase 2: {total_enriched} repositories enriched")
    print(f"💾 All data saved to PostgreSQL database")

def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description="GitHub Repository Scraper - Two-Phase Architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app.main                # Run both phases (default)
  python -m app.main --phase1-only  # Fast basic collection
  python -m app.main --phase2-only  # Detailed enrichment only
  python -m app.main --stats        # Show database statistics
        """
    )
    
    parser.add_argument('--phase1-only', action='store_true',
                       help='Run only Phase 1 (fast basic collection)')
    parser.add_argument('--phase2-only', action='store_true',
                       help='Run only Phase 2 (detailed enrichment)')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics and exit')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Handle statistics mode
    if args.stats:
        show_database_stats()
        return
    
    # Validate arguments
    if args.phase1_only and args.phase2_only:
        print("❌ Cannot specify both --phase1-only and --phase2-only")
        sys.exit(1)
    
    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("🐙 GitHub Repository Scraper - Two-Phase Architecture")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check database connection
    if not ensure_connection():
        print("❌ Cannot connect to database. Make sure PostgreSQL is running:")
        print("   docker-compose up -d")
        sys.exit(1)
    
    try:
        if args.phase1_only:
            run_phase1_only()
        elif args.phase2_only:
            run_phase2_only()
        else:
            run_both_phases()
            
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logging.exception("Unexpected error occurred")
        sys.exit(1)
    
    print("\n✨ All done! Check the database for your data.")

if __name__ == '__main__':
    main()