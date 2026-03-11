# Space-Track Integration for Sentinel Revisit Calculator

## Overview

This document describes the Space-Track integration added to the Sentinel Revisit Time Calculator. Space-Track provides the most accurate and up-to-date TLE (Two-Line Element) data for satellites.

## Changes Made

### 1. Code Changes in `sentinel_revisit_calculator.py`

#### Import Additions
- Added `os` module for environment variable access
- Added `Path` from `pathlib` for file path handling
- Added `python-dotenv` support (optional) for loading `.env` files

#### New Class Attributes
- `space_track_username`: Username for Space-Track authentication
- `space_track_password`: Password for Space-Track authentication
- `space_track_session`: Requests session for maintaining authentication

#### New Methods

**`_authenticate_space_track(self) -> bool`**
- Authenticates with Space-Track API
- Creates a persistent session for API requests
- Returns True if authentication is successful
- Credentials are read from environment variables or constructor parameters

**`_get_tle_from_space_track(self, norad_id: int) -> Optional[Tuple[str, str]]`**
- Fetches TLE data from Space-Track for a given NORAD ID
- Uses the authenticated session
- Returns tuple of (line1, line2) TLE data
- Automatically re-authenticates if session expires
- Falls back to Celestrak if Space-Track fails

#### Modified Methods

**`__init__()`**
- Added `space_track_username` parameter (optional)
- Added `space_track_password` parameter (optional)
- Reads credentials from environment variables if not provided
- Initializes Space-Track session attribute

**`get_tle_data()`**
- Modified to use Space-Track when `tle_source='space_track'`
- Implements automatic fallback to Celestrak if Space-Track fails
- Maintains backward compatibility with existing Celestrak sources

#### Command Line Arguments

Added new CLI arguments:
- `--space_track_username`: Space-Track username (overrides environment variable)
- `--space_track_password`: Space-Track password (overrides environment variable)
- Changed default `--tle_source` from `celestrak_active` to `space_track`

### 2. Documentation Updates

#### Updated `sentinel_revisit_calculator.py` docstring
- Added Space-Track information
- Updated usage examples
- Added python-dotenv to requirements

#### Updated `SENTINEL_REVISIT_README.md`

**Features Section:**
- Added "Space-Track Authentication" feature

**New "Space-Track Setup" Section:**
- Instructions for registering for Space-Track
- How to create and configure `.env` file
- Testing instructions
- Alternative Celestrak usage without authentication

**Updated "Optional Arguments" Section:**
- Added `--space_track_username` and `--space_track_password` arguments
- Updated default `--tle_source` to `space_track`

**Updated "TLE Data Sources" Section:**
- Comprehensive explanation of all three TLE sources
- Space-Track marked as default and recommended
- Authentication requirements for each source

**Updated "Troubleshooting" Section:**
- Added Space-Track specific troubleshooting steps
- Credential verification steps
- Fallback instructions

**Updated "References" Section:**
- Added Space-Track API link

## Usage

### Using Space-Track (Recommended)

1. **Register for Space-Track**:
   ```bash
   # Visit https://www.space-track.org/auth/createAccount
   ```

2. **Create `.env` file** in project root:
   ```bash
   SPACE_TRACK_ID=your_username
   SPACE_TRACK_PASSWORD=your_password
   ```

3. **Run the calculator** (Space-Track is now the default):
   ```bash
   pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py \
       --latitude 40.7128 --longitude -74.0060 \
       --start_date 2024-01-01 --end_date 2024-01-31
   ```

### Using Celestrak (No Authentication)

```bash
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py \
    --latitude 40.7128 --longitude -74.0060 \
    --start_date 2024-01-01 --end_date 2024-01-31 \
    --tle_source celestrak_active
```

### Programmatic Usage

```python
from sentinel_revisit_times.sentinel_revisit_calculator import SentinelRevisitCalculator

# Using Space-Track (reads from environment variables)
calculator = SentinelRevisitCalculator(tle_source='space_track')

# Using Space-Track with explicit credentials
calculator = SentinelRevisitCalculator(
    tle_source='space_track',
    space_track_username='your_username',
    space_track_password='your_password'
)

# Using Celestrak (no authentication needed)
calculator = SentinelRevisitCalculator(tle_source='celestrak_active')
```

## Environment Variables

The integration uses the following environment variables:

- `SPACE_TRACK_ID`: Your Space-Track username
- `SPACE_TRACK_PASSWORD`: Your Space-Track password

These can be set in:
1. A `.env` file in the project root (recommended)
2. System environment variables
3. Passed directly as constructor parameters

## Security

- The `.env` file is automatically ignored by git (listed in `.gitignore`)
- Never commit credentials to version control
- Credentials can be passed as command-line arguments for CI/CD environments
- Use environment-specific credential management in production

## Fallback Behavior

The integration includes robust fallback behavior:

1. If Space-Track credentials are not provided, logs an error
2. If Space-Track authentication fails, automatically falls back to Celestrak
3. If Space-Track TLE fetch fails, automatically falls back to Celestrak
4. If session expires, automatically re-authenticates

This ensures the tool always works, even if Space-Track is unavailable.

## Benefits of Space-Track

1. **More Accurate**: Space-Track TLE data is updated more frequently
2. **Authoritative Source**: Official source for US Space Surveillance Network data
3. **Better Coverage**: May have TLE data for satellites not available on Celestrak
4. **Historical Data**: Access to historical TLE data sets

## API Details

### Space-Track Authentication

- **Endpoint**: `https://www.space-track.org/ajaxauth/login`
- **Method**: POST
- **Payload**: `identity` (username) and `password`
- **Session**: Cookie-based authentication

### Space-Track TLE Query

- **Endpoint**: `https://www.space-track.org/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/{norad_id}/orderby/EPOCH%20desc/limit/1/format/tle`
- **Method**: GET (with authenticated session)
- **Response**: 2-line TLE format (no name line)

## Testing

To test the Space-Track integration:

```bash
# Test with Space-Track
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py \
    --latitude 40.7128 --longitude -74.0060 \
    --start_date 2024-01-01 --end_date 2024-01-07 \
    --satellites Sentinel-1A \
    --verbose

# Test with Celestrak fallback (without .env file)
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py \
    --latitude 40.7128 --longitude -74.0060 \
    --start_date 2024-01-01 --end_date 2024-01-07 \
    --satellites Sentinel-1A \
    --tle_source celestrak_active \
    --verbose
```

## Backward Compatibility

The changes maintain full backward compatibility:

- Default behavior now uses Space-Track (if credentials available)
- Existing code using Celestrak continues to work unchanged
- CLI argument defaults changed, but can be overridden
- All existing functionality remains intact

## Future Enhancements

Potential future improvements:

1. Cache TLE data locally to reduce API calls
2. Support for batch TLE queries for multiple satellites
3. Historical TLE data retrieval for specific epochs
4. Rate limiting to respect Space-Track API limits
5. Retry logic with exponential backoff
6. Support for other TLE sources (e.g., SpaceX, Planet)

