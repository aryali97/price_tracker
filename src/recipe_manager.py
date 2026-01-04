"""
Manager for extraction recipes - orchestrates learn/direct/fallback logic.
"""

from typing import Dict, Any, Optional
from .database import Database


class RecipeManager:
    """Manages extraction recipes and mode selection."""

    def __init__(self, db: Database):
        """
        Initialize recipe manager.

        Args:
            db: Database instance
        """
        self.db = db

    def get_active_recipe(self, site_domain: str) -> Optional[Dict[str, Any]]:
        """
        Get the active recipe for a site.

        Args:
            site_domain: Site domain (e.g., 'abercrombie.com')

        Returns:
            Recipe dict or None if no active recipe exists
        """
        return self.db.get_active_recipe(site_domain)

    def should_use_learn_mode(self, site_domain: str, url: str) -> bool:
        """
        Determine if should use learn mode.

        Learn mode is triggered when:
        1. No recipe exists for this site
        2. Existing recipe has high failure rate (>30%)

        Args:
            site_domain: Site domain
            url: Specific URL being scraped (currently unused, for future expansion)

        Returns:
            True if should use learn mode
        """
        recipe = self.get_active_recipe(site_domain)

        # No recipe exists - must learn
        if not recipe:
            print(f"[RecipeManager] No recipe found for {site_domain} - using learn mode")
            return True

        # Check failure rate
        total_uses = recipe['success_count'] + recipe['failure_count']
        if total_uses > 10:  # Only check if we have enough data
            failure_rate = recipe['failure_count'] / total_uses
            if failure_rate > 0.3:  # 30% threshold
                print(
                    f"[RecipeManager] Recipe failure rate {failure_rate:.1%} "
                    f"(threshold: 30%) - triggering re-learn"
                )
                return True

        # Recipe is good - use direct mode
        return False

    def save_learned_recipe(self, site_domain: str, recipe_data: Dict[str, Any]) -> int:
        """
        Save a newly learned recipe.

        If a recipe already exists, this creates a new version and marks old as inactive.

        Args:
            site_domain: Site domain (e.g., 'abercrombie.com')
            recipe_data: Recipe dictionary with selectors

        Returns:
            Recipe ID
        """
        # Get current max version
        existing = self.db.get_all_recipes(site_domain)
        next_version = max([r['recipe_version'] for r in existing], default=0) + 1

        # Mark existing recipes as inactive
        for recipe in existing:
            if recipe['is_active']:
                self.db.mark_recipe_inactive(recipe['id'])
                print(f"[RecipeManager] Marked recipe v{recipe['recipe_version']} as inactive")

        # Save new recipe
        recipe_id = self.db.insert_recipe(
            site_domain=site_domain,
            recipe_version=next_version,
            selectors=recipe_data
        )

        print(f"[RecipeManager] ✓ Saved new recipe v{next_version} for {site_domain} (ID: {recipe_id})")
        return recipe_id

    def record_success(self, recipe_id: int, confidence: float):
        """
        Record successful extraction.

        Args:
            recipe_id: Recipe ID
            confidence: Extraction confidence score (0.0-1.0)
        """
        self.db.increment_recipe_success(recipe_id, confidence)

    def record_failure(self, recipe_id: int):
        """
        Record failed extraction.

        Args:
            recipe_id: Recipe ID
        """
        self.db.increment_recipe_failure(recipe_id)
