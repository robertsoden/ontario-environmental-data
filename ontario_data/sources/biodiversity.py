"""Biodiversity data source clients for Ontario.

Provides clients for:
- iNaturalist: Research-grade biodiversity observations
- eBird: Bird observation data
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

from ontario_data.sources.base import BaseClient, DataSourceError

logger = logging.getLogger(__name__)


class INaturalistClient(BaseClient):
    """Client for iNaturalist API v1.

    iNaturalist is a community science platform with millions of biodiversity
    observations worldwide. Ontario has 100K+ research-grade observations.

    API Documentation: https://api.inaturalist.org/v1/docs/

    No API key required. Rate limit: 60 requests/minute.
    """

    BASE_URL = "https://api.inaturalist.org/v1"
    ONTARIO_PLACE_ID = 6942

    def __init__(self, rate_limit: int = 60):
        """Initialize iNaturalist client.

        Args:
            rate_limit: Requests per minute (default 60)
        """
        super().__init__(rate_limit=rate_limit)

    async def get_observations(
        self,
        bounds: tuple[float, float, float, float],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        quality_grade: str = "research",
        per_page: int = 200,
        max_results: int = 1000,
    ) -> List[Dict]:
        """Get iNaturalist observations within geographic bounds.

        Args:
            bounds: Bounding box (swlat, swlng, nelat, nelng)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            quality_grade: Quality filter - "research", "needs_id", or "casual"
            per_page: Results per page (max 200)
            max_results: Maximum total results to fetch

        Returns:
            List of observation dictionaries

        Example:
            >>> client = INaturalistClient()
            >>> bounds = (44.0, -79.5, 45.0, -78.5)  # Peterborough area
            >>> observations = await client.get_observations(
            ...     bounds=bounds,
            ...     start_date="2024-01-01",
            ...     quality_grade="research"
            ... )
        """
        all_observations = []
        page = 1

        params = {
            "swlat": bounds[0],
            "swlng": bounds[1],
            "nelat": bounds[2],
            "nelng": bounds[3],
            "quality_grade": quality_grade,
            "geo": "true",
            "photos": "true",
            "per_page": min(per_page, 200),
            "page": page,
        }

        if start_date:
            params["d1"] = start_date
        if end_date:
            params["d2"] = end_date

        async with aiohttp.ClientSession() as session:
            while len(all_observations) < max_results:
                params["page"] = page
                url = f"{self.BASE_URL}/observations"

                try:
                    await self._rate_limit_wait()

                    async with session.get(url, params=params) as response:
                        if response.status != 200:
                            logger.warning(
                                f"iNaturalist API returned status {response.status}"
                            )
                            break

                        data = await response.json()
                        results = data.get("results", [])

                        if not results:
                            break

                        all_observations.extend(results)

                        # Check if we've reached the end
                        if len(results) < per_page:
                            break

                        page += 1

                except Exception as e:
                    logger.error(f"Error fetching iNaturalist data: {e}")
                    break

        logger.info(f"Fetched {len(all_observations)} iNaturalist observations")
        return all_observations[:max_results]

    async def fetch(
        self,
        bounds: tuple[float, float, float, float],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> List[Dict]:
        """Fetch observations (implements BaseClient.fetch).

        Args:
            bounds: Bounding box (swlat, swlng, nelat, nelng)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            **kwargs: Additional arguments passed to get_observations

        Returns:
            List of standardized observation dictionaries
        """
        observations = await self.get_observations(
            bounds=bounds,
            start_date=start_date,
            end_date=end_date,
            **kwargs,
        )
        return [self.transform_observation(obs) for obs in observations]

    @staticmethod
    def transform_observation(obs: dict) -> dict:
        """Transform iNaturalist observation to standardized format.

        Args:
            obs: Raw observation from iNaturalist API

        Returns:
            Standardized observation dictionary with GeoJSON Point
        """
        location_parts = obs.get("location", ",").split(",")

        return {
            "source": "iNaturalist",
            "observation_id": str(obs["id"]),
            "species_name": obs["taxon"]["name"],
            "common_name": obs["taxon"].get("preferred_common_name", ""),
            "scientific_name": obs["taxon"]["name"],
            "taxonomy": {
                "rank": obs["taxon"]["rank"],
                "iconic_taxon": obs["taxon"].get("iconic_taxon_name"),
                "taxon_id": obs["taxon"]["id"],
            },
            "observation_date": obs["observed_on"],
            "observation_datetime": obs.get("time_observed_at"),
            "location": {
                "type": "Point",
                "coordinates": [
                    float(location_parts[1]),  # longitude
                    float(location_parts[0]),  # latitude
                ],
            },
            "accuracy_meters": obs.get("positional_accuracy"),
            "place_name": obs.get("place_guess"),
            "quality_grade": obs["quality_grade"],
            "license": obs.get("license"),
            "observer": obs["user"]["login"],
            "photos": [photo["url"] for photo in obs.get("photos", [])],
            "identifications_count": obs.get("identifications_count", 0),
            "url": f"https://www.inaturalist.org/observations/{obs['id']}",
        }


class EBirdClient(BaseClient):
    """Client for eBird API 2.0.

    eBird is a real-time, online bird checklist program with millions of
    observations. Provides recent bird sightings and species distributions.

    API Documentation: https://documenter.getpostman.com/view/664302/S1ENwy59

    Requires free API key: https://ebird.org/api/keygen
    """

    BASE_URL = "https://api.ebird.org/v2"
    ONTARIO_REGION = "CA-ON"

    def __init__(self, api_key: str, rate_limit: int = 60):
        """Initialize eBird client.

        Args:
            api_key: eBird API key (get from https://ebird.org/api/keygen)
            rate_limit: Requests per minute (default 60)

        Raises:
            ValueError: If api_key is not provided
        """
        if not api_key:
            raise ValueError("eBird API key is required")

        super().__init__(rate_limit=rate_limit)
        self.api_key = api_key
        self.headers = {"x-ebirdapitoken": api_key}

    async def get_recent_observations(
        self,
        region_code: Optional[str] = None,
        back_days: int = 30,
        max_results: int = 1000,
    ) -> List[Dict]:
        """Get recent eBird observations for Ontario or specific region.

        Args:
            region_code: Regional code (default CA-ON for Ontario)
            back_days: Number of days back to search (1-30)
            max_results: Maximum results (1-10000)

        Returns:
            List of observation dictionaries

        Example:
            >>> client = EBirdClient(api_key="your_key")
            >>> observations = await client.get_recent_observations(
            ...     region_code="CA-ON-PB",  # Peterborough
            ...     back_days=7
            ... )
        """
        if region_code is None:
            region_code = self.ONTARIO_REGION

        url = f"{self.BASE_URL}/data/obs/{region_code}/recent"
        params = {
            "back": min(back_days, 30),
            "maxResults": min(max_results, 10000),
        }

        try:
            async with aiohttp.ClientSession() as session:
                await self._rate_limit_wait()

                async with session.get(
                    url, headers=self.headers, params=params
                ) as response:
                    if response.status != 200:
                        logger.warning(f"eBird API returned status {response.status}")
                        return []

                    observations = await response.json()
                    logger.info(f"Fetched {len(observations)} eBird observations")
                    return observations

        except Exception as e:
            logger.error(f"Error fetching eBird data: {e}")
            raise DataSourceError(f"eBird API error: {e}")

    async def fetch(
        self,
        region_code: Optional[str] = None,
        back_days: int = 30,
        **kwargs,
    ) -> List[Dict]:
        """Fetch observations (implements BaseClient.fetch).

        Args:
            region_code: Regional code (default CA-ON)
            back_days: Number of days back (1-30)
            **kwargs: Additional arguments passed to get_recent_observations

        Returns:
            List of standardized observation dictionaries
        """
        observations = await self.get_recent_observations(
            region_code=region_code,
            back_days=back_days,
            **kwargs,
        )
        return [self.transform_observation(obs) for obs in observations]

    @staticmethod
    def transform_observation(obs: dict) -> dict:
        """Transform eBird observation to standardized format.

        Args:
            obs: Raw observation from eBird API

        Returns:
            Standardized observation dictionary with GeoJSON Point
        """
        return {
            "source": "eBird",
            "observation_id": obs["subId"],
            "species_code": obs["speciesCode"],
            "common_name": obs["comName"],
            "scientific_name": obs["sciName"],
            "observation_datetime": obs["obsDt"],
            "location": {
                "type": "Point",
                "coordinates": [obs["lng"], obs["lat"]],
            },
            "location_name": obs["locName"],
            "location_id": obs["locId"],
            "count": obs.get("howMany"),
            "valid": obs.get("obsValid", True),
            "reviewed": obs.get("obsReviewed", False),
            "url": f"https://ebird.org/checklist/{obs['subId']}",
        }
