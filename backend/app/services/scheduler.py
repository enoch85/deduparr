"""
Background scheduler for automated duplicate scanning
"""

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Config, ScoringRule
from app.services.plex_service import PlexService
from app.services.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


class ScanScheduler:
    """Manages scheduled duplicate scans"""

    def __init__(self):
        """Initialize the scheduler"""
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    async def _get_enabled_libraries(self, db: AsyncSession) -> list[str]:
        """Get list of enabled Plex libraries from config"""
        result = await db.execute(
            select(Config).where(Config.key == "plex_libraries")
        )
        config = result.scalar_one_or_none()
        
        if not config or not config.value:
            logger.warning("No Plex libraries configured for scheduled scans")
            return []
        
        # Value is stored as comma-separated string
        libraries = [lib.strip() for lib in config.value.split(",") if lib.strip()]
        logger.info(f"Found {len(libraries)} configured libraries for scanning")
        return libraries

    async def _run_scheduled_scan(self):
        """Execute a scheduled duplicate scan"""
        logger.info("Starting scheduled duplicate scan")
        
        async with AsyncSessionLocal() as db:
            try:
                # Get enabled libraries
                libraries = await self._get_enabled_libraries(db)
                
                if not libraries:
                    logger.warning("No libraries configured - skipping scheduled scan")
                    return
                
                # Initialize services
                plex_service = PlexService(db)
                scoring_engine = ScoringEngine()
                
                # Get custom scoring rules
                rules_result = await db.execute(
                    select(ScoringRule).where(ScoringRule.enabled)
                )
                scoring_rules = rules_result.scalars().all()
                custom_rules = [
                    {
                        "pattern": rule.pattern,
                        "score_modifier": rule.score_modifier,
                        "rule_type": rule.rule_type.value,
                    }
                    for rule in scoring_rules
                ]
                
                # Import here to avoid circular dependency
                from app.api.routes.scan import (
                    _cleanup_stale_duplicate_sets,
                    _process_duplicate_movies,
                    _process_duplicate_episodes,
                )
                from app.models.duplicate import MediaType
                
                total_sets_created = 0
                total_sets_existing = 0
                
                # Scan each library
                for library_name in libraries:
                    try:
                        logger.info(f"Scanning library: {library_name}")
                        library = plex_service.get_library(library_name)
                        
                        if library.type == "movie":
                            movie_dupes = plex_service.find_duplicate_movies(library_name)
                            await _cleanup_stale_duplicate_sets(db, movie_dupes, MediaType.MOVIE)
                            sets_created, sets_existing = await _process_duplicate_movies(
                                db, movie_dupes, scoring_engine, custom_rules
                            )
                            total_sets_created += sets_created
                            total_sets_existing += sets_existing
                            
                        elif library.type == "show":
                            episode_dupes = plex_service.find_duplicate_episodes(library_name)
                            await _cleanup_stale_duplicate_sets(db, episode_dupes, MediaType.EPISODE)
                            sets_created, sets_existing = await _process_duplicate_episodes(
                                db, episode_dupes, scoring_engine, custom_rules
                            )
                            total_sets_created += sets_created
                            total_sets_existing += sets_existing
                        
                        else:
                            logger.warning(f"Unsupported library type: {library.type}")
                            
                    except Exception as e:
                        logger.error(f"Error scanning library '{library_name}': {e}", exc_info=True)
                        continue
                
                await db.commit()
                logger.info(
                    f"Scheduled scan complete: {total_sets_created} new sets, "
                    f"{total_sets_existing} existing sets"
                )
                
            except Exception as e:
                logger.error(f"Scheduled scan failed: {e}", exc_info=True)
                await db.rollback()

    async def start(self, interval_hours: int = 24):
        """
        Start the scheduler
        
        Args:
            interval_hours: How often to run scans (default: 24 hours)
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        logger.info(f"Starting scan scheduler with {interval_hours}h interval")
        
        # Add job to run at specified interval
        self.scheduler.add_job(
            self._run_scheduled_scan,
            trigger=IntervalTrigger(hours=interval_hours),
            id="duplicate_scan",
            name="Scheduled Duplicate Scan",
            replace_existing=True,
        )
        
        self.scheduler.start()
        self.is_running = True
        logger.info("Scan scheduler started successfully")

    async def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            return
        
        logger.info("Stopping scan scheduler")
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("Scan scheduler stopped")

    async def run_now(self):
        """Trigger an immediate scan (in addition to scheduled ones)"""
        logger.info("Triggering immediate scan")
        await self._run_scheduled_scan()


# Global scheduler instance
_scheduler: Optional[ScanScheduler] = None


def get_scheduler() -> ScanScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = ScanScheduler()
    return _scheduler
