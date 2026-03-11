#!/usr/bin/env python3
"""
Sentinel Revisit Time Calculator

This script calculates the revisit time for Sentinel-1 and Sentinel-2 satellites
over a specific location and time period using TLE (Two-Line Element) data.

Note: Sentinel-2 satellites (optical) are automatically filtered to daytime observations
only (solar zenith < 90°) since optical imagery cannot be captured during nighttime.
This behavior can be overridden with the --include_nighttime flag.

TLE Data Sources:
- Space-Track (default): Requires authentication via SPACE_TRACK_ID and SPACE_TRACK_PASSWORD 
  environment variables. More accurate and up-to-date TLE data.
- Celestrak: Public TLE data source, no authentication required.

Usage:
    # Using Space-Track (recommended, requires .env file with credentials):
    python sentinel_revisit_calculator.py --latitude 40.7128 --longitude -74.0060 \\
        --start_date 2024-01-01 --end_date 2024-01-31
    
    # Using Celestrak (no authentication required):
    python sentinel_revisit_calculator.py --latitude 40.7128 --longitude -74.0060 \\
        --start_date 2024-01-01 --end_date 2024-01-31 --tle_source celestrak_active
    
    # For daytime-only analysis (automatically applied to Sentinel-2):
    python sentinel_revisit_calculator.py --latitude 40.7128 --longitude -74.0060 \\
        --start_date 2024-01-01 --end_date 2024-01-31 --daytime_only
    
    # To include nighttime observations for Sentinel-2:
    python sentinel_revisit_calculator.py --latitude 40.7128 --longitude -74.0060 \\
        --start_date 2024-01-01 --end_date 2024-01-31 --include_nighttime

Requirements:
    - skyfield
    - pandas
    - numpy
    - requests
    - python-dotenv (optional, for loading .env files)
    - matplotlib (optional, for plotting)
"""

import argparse
import logging
import os
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from skyfield.api import EarthSatellite, load, wgs84
from skyfield.timelib import Time
from skyfield.positionlib import Apparent

# Try to import python-dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Sentinel satellite NORAD IDs
SENTINEL_SATELLITES = {
    'Sentinel-1A': 39634,
    # 'Sentinel-1B': 41456, # Not available
    'Sentinel-1C': 52860,
    # 'Sentinel-1D': 52861, # Not available
    # 'Sentinel-2A': 40697, # Not available
    'Sentinel-2B': 42063,
    'Sentinel-2C': 43653,
    # 'Sentinel-2D': 43654, # Not available
}

# TLE data sources
TLE_SOURCES = {
    'celestrak_active': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle',
    'celestrak_supplemental': 'https://celestrak.org/NORAD/elements/supplemental/',
    'space_track': 'https://www.space-track.org/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/{}/orderby/TLE_LINE1%20asc/format/tle',
}


class SentinelRevisitCalculator:
    """Calculate revisit times for Sentinel satellites."""
    
    def __init__(self, tle_source: str = 'space_track', space_track_username: Optional[str] = None, 
                 space_track_password: Optional[str] = None):
        """
        Initialize the calculator.
        
        Args:
            tle_source: Source for TLE data ('celestrak_active', 'celestrak_supplemental', or 'space_track')
            space_track_username: Space-Track username (if not provided, will read from SPACE_TRACK_ID env var)
            space_track_password: Space-Track password (if not provided, will read from SPACE_TRACK_PASSWORD env var)
        """
        self.tle_source = tle_source
        self.ts = load.timescale()
        self.satellites = {}
        self.ephemeris = load('de421.bsp')  # Load ephemeris for solar calculations
        
        # Space-Track credentials
        self.space_track_username = space_track_username or os.getenv('SPACE_TRACK_ID')
        self.space_track_password = space_track_password or os.getenv('SPACE_TRACK_PASSWORD')
        self.space_track_session = None
    
    def _authenticate_space_track(self) -> bool:
        """
        Authenticate with Space-Track API.
        
        Returns:
            True if authentication successful, False otherwise
        """
        if not self.space_track_username or not self.space_track_password:
            logger.error("Space-Track credentials not found. Please set SPACE_TRACK_ID and SPACE_TRACK_PASSWORD environment variables.")
            return False
        
        try:
            # Create a session for Space-Track
            if self.space_track_session is None:
                self.space_track_session = requests.Session()
            
            # Login to Space-Track
            login_url = 'https://www.space-track.org/ajaxauth/login'
            login_data = {
                'identity': self.space_track_username,
                'password': self.space_track_password
            }
            
            response = self.space_track_session.post(login_url, data=login_data, timeout=30)
            response.raise_for_status()
            
            logger.info("Successfully authenticated with Space-Track")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to authenticate with Space-Track: {e}")
            return False
    
    def _get_tle_from_space_track(self, norad_id: int) -> Optional[Tuple[str, str]]:
        """
        Fetch TLE data from Space-Track.
        
        Args:
            norad_id: NORAD ID of the satellite
            
        Returns:
            Tuple of (line1, line2) TLE data or None if not found
        """
        try:
            # Authenticate if not already authenticated
            if self.space_track_session is None:
                if not self._authenticate_space_track():
                    return None
            
            # Query TLE data
            query_url = f'https://www.space-track.org/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/{norad_id}/orderby/EPOCH%20desc/limit/1/format/tle'
            
            response = self.space_track_session.get(query_url, timeout=30)
            response.raise_for_status()
            
            # Parse TLE response
            tle_text = response.text.strip()
            if not tle_text:
                logger.warning(f"No TLE data found for NORAD ID {norad_id}")
                return None
            
            lines = tle_text.split('\n')
            if len(lines) >= 2:
                # Space-Track returns TLE in 2-line format (no name line)
                line1 = lines[0].strip()
                line2 = lines[1].strip()
                
                logger.info(f"Successfully fetched TLE data from Space-Track for NORAD ID {norad_id}")
                return line1, line2
            else:
                logger.warning(f"Invalid TLE format from Space-Track for NORAD ID {norad_id}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Failed to fetch TLE from Space-Track for NORAD ID {norad_id}: {e}")
            # Try to re-authenticate if session expired
            self.space_track_session = None
            return None
        
    def get_tle_data(self, satellite_name: str, norad_id: int) -> Optional[Tuple[str, str]]:
        """
        Fetch TLE data for a satellite.
        
        Args:
            satellite_name: Name of the satellite
            norad_id: NORAD ID of the satellite
            
        Returns:
            Tuple of (line1, line2) TLE data or None if not found
        """
        try:
            if self.tle_source == 'celestrak_active':
                response = requests.get(TLE_SOURCES['celestrak_active'], timeout=30)
                response.raise_for_status()
                
                lines = response.text.strip().split('\n')
                for i in range(0, len(lines), 3):
                    if len(lines) >= i + 3:
                        name_line = lines[i].strip()
                        line1 = lines[i + 1].strip()
                        line2 = lines[i + 2].strip()
                        
                        # Check by NORAD ID in line1 (characters 3-7)
                        if len(line1) >= 7 and line1[2:7] == str(norad_id):
                            logger.info(f"Found TLE data for {satellite_name} (NORAD ID: {norad_id})")
                            return line1, line2
                            
            elif self.tle_source == 'celestrak_supplemental':
                # Try to find Sentinel-specific files
                try:
                    # Try different possible Sentinel file names
                    possible_files = [
                        'sentinel.txt',
                        'copernicus.txt',
                        'esa.txt'
                    ]
                    
                    for filename in possible_files:
                        url = f"https://celestrak.org/NORAD/elements/supplemental/{filename}"
                        try:
                            response = requests.get(url, timeout=30)
                            if response.status_code == 200:
                                lines = response.text.strip().split('\n')
                                for i in range(0, len(lines), 3):
                                    if len(lines) >= i + 3:
                                        name_line = lines[i].strip()
                                        line1 = lines[i + 1].strip()
                                        line2 = lines[i + 2].strip()
                                        
                                        if satellite_name.lower() in name_line.lower():
                                            logger.info(f"Found TLE data for {satellite_name}")
                                            return line1, line2
                        except requests.RequestException:
                            continue
                            
                except Exception as e:
                    logger.debug(f"Failed to fetch from supplemental: {e}")
                    
            elif self.tle_source == 'space_track':
                # Use Space-Track API
                tle_data = self._get_tle_from_space_track(norad_id)
                if tle_data is not None:
                    return tle_data
                else:
                    logger.warning(f"Failed to get TLE from Space-Track for {satellite_name}, falling back to Celestrak")
                    # Fallback to Celestrak
                    original_source = self.tle_source
                    self.tle_source = 'celestrak_active'
                    result = self.get_tle_data(satellite_name, norad_id)
                    self.tle_source = original_source
                    return result
                
        except requests.RequestException as e:
            logger.error(f"Failed to fetch TLE data for {satellite_name}: {e}")
            
        return None
    
    def create_satellite(self, satellite_name: str, norad_id: int) -> Optional[EarthSatellite]:
        """
        Create a satellite object from TLE data.
        
        Args:
            satellite_name: Name of the satellite
            norad_id: NORAD ID of the satellite
            
        Returns:
            EarthSatellite object or None if creation failed
        """
        tle_data = self.get_tle_data(satellite_name, norad_id)
        if tle_data is None:
            logger.warning(f"Could not get TLE data for {satellite_name}")
            return None
            
        line1, line2 = tle_data
        
        try:
            satellite = EarthSatellite(line1, line2, satellite_name, self.ts)
            logger.info(f"Successfully created satellite object for {satellite_name}")
            return satellite
        except Exception as e:
            logger.error(f"Failed to create satellite object for {satellite_name}: {e}")
            return None
    
    def calculate_solar_zenith_angle(self, latitude: float, longitude: float, time: datetime) -> float:
        """
        Calculate solar zenith angle at a specific location and time.
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            time: Datetime object
            
        Returns:
            Solar zenith angle in degrees
        """
        try:
            # Convert datetime to skyfield time
            ts = self.ts.utc(
                time.year, time.month, time.day,
                time.hour, time.minute, time.second
            )
            
            # Get observer location
            observer = wgs84.latlon(latitude, longitude)
            
            # Get Sun position
            sun = self.ephemeris['sun']
            earth = self.ephemeris['earth']
            
            # Calculate apparent position of sun from observer
            apparent = observer.at(ts).observe(sun).apparent()
            
            # Get altitude and azimuth
            alt, az, distance = apparent.altaz()
            
            # Solar zenith angle = 90° - altitude
            solar_zenith = 90.0 - alt.degrees
            
            return solar_zenith
            
        except Exception as e:
            logger.warning(f"Failed to calculate solar zenith angle: {e}")
            return 90.0  # Default to 90° (horizon) if calculation fails
    
    def is_sentinel_2_satellite(self, satellite_name: str) -> bool:
        """
        Check if a satellite is a Sentinel-2 (optical) satellite.
        
        Args:
            satellite_name: Name of the satellite
            
        Returns:
            True if it's a Sentinel-2 satellite, False otherwise
        """
        return satellite_name.startswith('Sentinel-2')
    
    def find_satellite_passes(
        self,
        satellite: EarthSatellite,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime,
        minimum_elevation: float = 10.0,
        filter_daytime_only: bool = False
    ) -> List[datetime]:
        """
        Find all satellite passes over a location.
        
        Args:
            satellite: EarthSatellite object
            latitude: Target latitude in degrees
            longitude: Target longitude in degrees
            start_time: Start of time window
            end_time: End of time window
            minimum_elevation: Minimum elevation angle in degrees
            filter_daytime_only: If True, filter to daytime passes only (solar zenith < 90°)
            
        Returns:
            List of datetime objects representing pass times
        """
        target_location = wgs84.latlon(latitude, longitude)
        
        # Convert to skyfield times
        start_ts = self.ts.utc(
            start_time.year, start_time.month, start_time.day,
            start_time.hour, start_time.minute, start_time.second
        )
        end_ts = self.ts.utc(
            end_time.year, end_time.month, end_time.day,
            end_time.hour, end_time.minute, end_time.second
        )
        
        # Find events (rise, culminate, set)
        times, events = satellite.find_events(
            target_location, start_ts, end_ts, altitude_degrees=minimum_elevation
        )
        
        # Extract culminate events (highest point in pass)
        culminate_times = times[np.where(events == 1)]
        
        # Convert to datetime objects
        pass_times = [t.utc_datetime() for t in culminate_times]
        
        # Filter to daytime passes only if requested
        if filter_daytime_only:
            daytime_passes = []
            for pass_time in pass_times:
                solar_zenith = self.calculate_solar_zenith_angle(latitude, longitude, pass_time)
                if solar_zenith < 90.0:  # Daytime condition
                    daytime_passes.append(pass_time)
            
            logger.info(f"Found {len(pass_times)} total passes, {len(daytime_passes)} daytime passes for {satellite.name}")
            return daytime_passes
        else:
            logger.info(f"Found {len(pass_times)} passes for {satellite.name}")
            return pass_times
    
    def calculate_revisit_times(self, pass_times: List[datetime]) -> Dict[str, Any]:
        """
        Calculate revisit time statistics from pass times.
        
        Args:
            pass_times: List of datetime objects representing pass times
            
        Returns:
            Dictionary containing revisit time statistics
        """
        if len(pass_times) < 2:
            return {
                'total_passes': len(pass_times),
                'average_revisit_time_days': None,
                'median_revisit_time_days': None,
                'min_revisit_time_days': None,
                'max_revisit_time_days': None,
                'revisit_times_hours': [],
                'pass_times': pass_times
            }
        
        # Sort pass times
        pass_times_sorted = sorted(pass_times)
        
        # Calculate time differences between consecutive passes
        revisit_times_hours = []
        for i in range(1, len(pass_times_sorted)):
            time_diff = pass_times_sorted[i] - pass_times_sorted[i-1]
            revisit_times_hours.append(time_diff.total_seconds() / 3600)
        
        revisit_times_days = [rt / 24 for rt in revisit_times_hours]
        
        return {
            'total_passes': len(pass_times),
            'average_revisit_time_days': np.mean(revisit_times_days),
            'median_revisit_time_days': np.median(revisit_times_days),
            'min_revisit_time_days': np.min(revisit_times_days),
            'max_revisit_time_days': np.max(revisit_times_days),
            'revisit_times_hours': revisit_times_hours,
            'pass_times': pass_times_sorted
        }
    
    def calculate_revisit_for_satellite(
        self,
        satellite_name: str,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        minimum_elevation: float = 10.0,
        force_daytime_only: bool = False,
        include_nighttime: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate revisit time for a specific satellite.
        
        Args:
            satellite_name: Name of the satellite
            latitude: Target latitude in degrees
            longitude: Target longitude in degrees
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            minimum_elevation: Minimum elevation angle in degrees
            force_daytime_only: Force daytime filtering for all satellites
            include_nighttime: Include nighttime observations (overrides automatic Sentinel-2 filtering)
            
        Returns:
            Dictionary containing revisit time statistics or None if failed
        """
        if satellite_name not in SENTINEL_SATELLITES:
            logger.error(f"Unknown satellite: {satellite_name}")
            return None
        
        norad_id = SENTINEL_SATELLITES[satellite_name]
        
        # Create satellite object
        satellite = self.create_satellite(satellite_name, norad_id)
        if satellite is None:
            return None
        
        # Parse dates
        try:
            start_time = datetime.strptime(start_date, '%Y-%m-%d')
            end_time = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Include end date
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return None
        
        # Determine daytime filtering logic
        if include_nighttime:
            # Override automatic filtering - include all passes
            filter_daytime = False
        elif force_daytime_only:
            # Force daytime filtering for all satellites
            filter_daytime = True
        else:
            # Automatic filtering: daytime only for Sentinel-2 satellites
            filter_daytime = self.is_sentinel_2_satellite(satellite_name)
        
        pass_times = self.find_satellite_passes(
            satellite, latitude, longitude, start_time, end_time, minimum_elevation, filter_daytime
        )
        
        # Calculate revisit times
        revisit_stats = self.calculate_revisit_times(pass_times)
        revisit_stats['satellite'] = satellite_name
        revisit_stats['location'] = f"{latitude:.4f}, {longitude:.4f}"
        revisit_stats['time_period'] = f"{start_date} to {end_date}"
        
        return revisit_stats
    
    def calculate_revisit_for_all_sentinels(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        minimum_elevation: float = 10.0,
        satellites: Optional[List[str]] = None,
        force_daytime_only: bool = False,
        include_nighttime: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate revisit times for all Sentinel satellites.
        
        Args:
            latitude: Target latitude in degrees
            longitude: Target longitude in degrees
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            minimum_elevation: Minimum elevation angle in degrees
            satellites: List of satellite names to analyze (default: all)
            force_daytime_only: Force daytime filtering for all satellites
            include_nighttime: Include nighttime observations (overrides automatic Sentinel-2 filtering)
            
        Returns:
            Dictionary mapping satellite names to their revisit statistics
        """
        if satellites is None:
            satellites = list(SENTINEL_SATELLITES.keys())
        
        results = {}
        
        for satellite_name in satellites:
            logger.info(f"Calculating revisit time for {satellite_name}...")
            result = self.calculate_revisit_for_satellite(
                satellite_name, latitude, longitude, start_date, end_date, minimum_elevation,
                force_daytime_only, include_nighttime
            )
            if result is not None:
                results[satellite_name] = result
            else:
                logger.warning(f"Failed to calculate revisit time for {satellite_name}")
        
        return results


def format_results(results: Dict[str, Dict[str, Any]]) -> str:
    """Format results for display."""
    output = []
    output.append("=" * 80)
    output.append("SENTINEL SATELLITE REVISIT TIME ANALYSIS")
    output.append("=" * 80)
    
    for satellite_name, stats in results.items():
        output.append(f"\n{satellite_name}")
        output.append("-" * len(satellite_name))
        output.append(f"Location: {stats['location']}")
        output.append(f"Time Period: {stats['time_period']}")
        output.append(f"Total Passes: {stats['total_passes']}")
        
        if stats['total_passes'] > 1:
            output.append(f"Average Revisit Time: {stats['average_revisit_time_days']:.2f} days")
            output.append(f"Median Revisit Time: {stats['median_revisit_time_days']:.2f} days")
            output.append(f"Min Revisit Time: {stats['min_revisit_time_days']:.2f} days")
            output.append(f"Max Revisit Time: {stats['max_revisit_time_days']:.2f} days")
            
            # Show individual pass times
            output.append(f"\nPass Times ({len(stats['pass_times'])} total):")
            for i, pass_time in enumerate(stats['pass_times'], 1):
                output.append(f"  {i:2d}. {pass_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        else:
            output.append("Insufficient data for revisit time calculation")
    
    return "\n".join(output)


def save_results_to_csv(results: Dict[str, Dict[str, Any]], filename: str):
    """Save results to CSV file."""
    rows = []
    for satellite_name, stats in results.items():
        row = {
            'satellite': satellite_name,
            'location': stats['location'],
            'time_period': stats['time_period'],
            'total_passes': stats['total_passes'],
            'average_revisit_time_days': stats['average_revisit_time_days'],
            'median_revisit_time_days': stats['median_revisit_time_days'],
            'min_revisit_time_days': stats['min_revisit_time_days'],
            'max_revisit_time_days': stats['max_revisit_time_days']
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False)
    logger.info(f"Results saved to {filename}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Calculate revisit times for Sentinel-1 and Sentinel-2 satellites"
    )
    parser.add_argument(
        '--latitude', '-lat', type=float, required=True,
        help='Target latitude in degrees'
    )
    parser.add_argument(
        '--longitude', '-lon', type=float, required=True,
        help='Target longitude in degrees'
    )
    parser.add_argument(
        '--start_date', '-s', type=str, required=True,
        help='Start date in YYYY-MM-DD format'
    )
    parser.add_argument(
        '--end_date', '-e', type=str, required=True,
        help='End date in YYYY-MM-DD format'
    )
    parser.add_argument(
        '--minimum_elevation', '-el', type=float, default=10.0,
        help='Minimum elevation angle in degrees (default: 10.0)'
    )
    parser.add_argument(
        '--satellites', '-sat', nargs='+', 
        choices=list(SENTINEL_SATELLITES.keys()),
        help='Specific satellites to analyze (default: all)'
    )
    parser.add_argument(
        '--output_csv', '-o', type=str,
        help='Output CSV filename'
    )
    parser.add_argument(
        '--tle_source', choices=['celestrak_active', 'celestrak_supplemental', 'space_track'], default='space_track',
        help='TLE data source (default: space_track)'
    )
    parser.add_argument(
        '--space_track_username', type=str,
        help='Space-Track username (default: read from SPACE_TRACK_ID environment variable)'
    )
    parser.add_argument(
        '--space_track_password', type=str,
        help='Space-Track password (default: read from SPACE_TRACK_PASSWORD environment variable)'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--daytime_only', action='store_true',
        help='Filter to daytime observations only (solar zenith < 90°). Automatically applied to Sentinel-2 satellites.'
    )
    parser.add_argument(
        '--include_nighttime', action='store_true',
        help='Include nighttime observations for Sentinel-2 satellites (overrides automatic daytime filtering)'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate coordinates
    if not (-90 <= args.latitude <= 90):
        logger.error("Latitude must be between -90 and 90 degrees")
        return 1
    
    if not (-180 <= args.longitude <= 180):
        logger.error("Longitude must be between -180 and 180 degrees")
        return 1
    
    # Create calculator
    calculator = SentinelRevisitCalculator(
        tle_source=args.tle_source,
        space_track_username=args.space_track_username,
        space_track_password=args.space_track_password
    )
    
    # Calculate revisit times
    logger.info(f"Calculating revisit times for location ({args.latitude}, {args.longitude})")
    logger.info(f"Time period: {args.start_date} to {args.end_date}")
    
    results = calculator.calculate_revisit_for_all_sentinels(
        latitude=args.latitude,
        longitude=args.longitude,
        start_date=args.start_date,
        end_date=args.end_date,
        minimum_elevation=args.minimum_elevation,
        satellites=args.satellites,
        force_daytime_only=args.daytime_only,
        include_nighttime=args.include_nighttime
    )
    
    if not results:
        logger.error("No results obtained. Check your parameters and internet connection.")
        return 1
    
    # Display results
    print(format_results(results))
    
    # Save to CSV if requested
    if args.output_csv:
        save_results_to_csv(results, args.output_csv)
    
    return 0


if __name__ == "__main__":
    exit(main())
