# Sentinel Revisit Time Calculator

A Python script to calculate revisit times for Sentinel-1 and Sentinel-2 satellites from the Copernicus program over specific locations and time periods.

## Features

- **Multiple Satellite Support**: Analyzes Sentinel-1A, Sentinel-1B, Sentinel-1C, Sentinel-1D, Sentinel-2A, Sentinel-2B, Sentinel-2C, and Sentinel-2D
- **Flexible Input**: Specify any location (latitude/longitude) and time period
- **Comprehensive Statistics**: Calculates average, median, minimum, and maximum revisit times
- **Multiple Output Formats**: Console output and CSV export
- **TLE Data Integration**: Uses real-time Two-Line Element (TLE) data from Space-Track or Celestrak
- **Space-Track Authentication**: Secure integration with Space-Track API for the most up-to-date TLE data
- **Configurable Parameters**: Adjustable minimum elevation angle and satellite selection
- **Daytime Filtering**: Automatic daytime-only filtering for Sentinel-2 satellites (optical imagery)
- **Solar Zenith Calculations**: Precise solar position calculations for realistic optical satellite analysis

## Installation

This project uses [pixi](https://pixi.sh/) for environment and dependency management.

### Prerequisites

1. Install pixi by following the [official installation guide](https://pixi.sh/installation/):
   ```bash
   # On macOS/Linux
   curl -fsSL https://pixi.sh/install.sh | bash
   
   # On Windows
   powershell -c "irm https://pixi.sh/install.ps1 | iex"
   ```

2. Internet connection (for TLE data)

### Environment Setup

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone <repository-url>
   cd capturing_peak_flood_conditions_project
   ```

2. Install dependencies using pixi:
   ```bash
   pixi install
   ```

3. Activate the environment:
   ```bash
   pixi shell
   ```

### Dependencies

The following packages are automatically installed via pixi:
- `skyfield` - Astronomical calculations and satellite tracking
- `pandas` - Data manipulation and analysis
- `numpy` - Numerical computing
- `requests` - HTTP library for TLE data fetching
- `matplotlib` - Plotting and visualization
- `python-dotenv` - Load environment variables from .env file (optional)

### Space-Track Setup (Recommended)

Space-Track provides the most accurate and up-to-date TLE (Two-Line Element) data for satellites. It's the default source for this tool.

1. **Register for a free Space-Track account**:
   - Visit https://www.space-track.org/auth/createAccount
   - Fill out the registration form
   - Verify your email address

2. **Create a `.env` file** in the project root directory:
   ```bash
   # In the project root: capturing_peak_flood_conditions_project/
   touch .env
   ```

3. **Add your credentials** to the `.env` file:
   ```
   SPACE_TRACK_ID=your_username_here
   SPACE_TRACK_PASSWORD=your_password_here
   ```

4. **Test your setup**:
   ```bash
   pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py --latitude 40.7128 --longitude -74.0060 --start_date 2024-01-01 --end_date 2024-01-31
   ```

**Alternative: Use Celestrak (No Authentication Required)**

If you don't want to register for Space-Track, you can use Celestrak as an alternative:
```bash
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py --latitude 40.7128 --longitude -74.0060 --start_date 2024-01-01 --end_date 2024-01-31 --tle_source celestrak_active
```

**Note**: The `.env` file is automatically ignored by git (listed in `.gitignore`) to keep your credentials secure.

## Usage

### Command Line Interface

```bash
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py --latitude 40.7128 --longitude -74.0060 --start_date 2024-01-01 --end_date 2024-01-31
```

#### Required Arguments

- `--latitude` or `-lat`: Target latitude in degrees (-90 to 90)
- `--longitude` or `-lon`: Target longitude in degrees (-180 to 180)
- `--start_date` or `-s`: Start date in YYYY-MM-DD format
- `--end_date` or `-e`: End date in YYYY-MM-DD format

#### Optional Arguments

- `--minimum_elevation` or `-el`: Minimum elevation angle in degrees (default: 10.0)
- `--satellites` or `-sat`: Specific satellites to analyze (default: all)
- `--output_csv` or `-o`: Output CSV filename
- `--tle_source`: TLE data source ('celestrak_active', 'celestrak_supplemental', or 'space_track', default: 'space_track')
- `--space_track_username`: Space-Track username (default: read from SPACE_TRACK_ID environment variable)
- `--space_track_password`: Space-Track password (default: read from SPACE_TRACK_PASSWORD environment variable)
- `--verbose` or `-v`: Enable verbose logging
- `--daytime_only`: Filter to daytime observations only (solar zenith < 90°). Automatically applied to Sentinel-2 satellites
- `--include_nighttime`: Include nighttime observations for Sentinel-2 satellites (overrides automatic daytime filtering)

### Examples

#### Basic Usage
```bash
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py -lat 40.7128 -lon -74.0060 -s 2024-01-01 -e 2024-01-31
```

#### Analyze Specific Satellites
```bash
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py -lat 51.5074 -lon -0.1278 -s 2024-01-01 -e 2024-01-31 -sat Sentinel-1A Sentinel-2A
```

#### Save Results to CSV
```bash
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py -lat 35.6762 -lon 139.6503 -s 2024-01-01 -e 2024-01-31 -o tokyo_revisit.csv
```

#### High Elevation Analysis
```bash
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py -lat -33.8688 -lon 151.2093 -s 2024-01-01 -e 2024-01-31 -el 30.0
```

#### Daytime-Only Analysis (All Satellites)
```bash
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py -lat 40.7128 -lon -74.0060 -s 2024-01-01 -e 2024-01-31 --daytime_only
```

#### Include Nighttime Observations for Sentinel-2
```bash
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py -lat 40.7128 -lon -74.0060 -s 2024-01-01 -e 2024-01-31 --include_nighttime
```

#### Sentinel-2 Only with Daytime Filtering (Default Behavior)
```bash
pixi run python sentinel_revisit_times/sentinel_revisit_calculator.py -lat 40.7128 -lon -74.0060 -s 2024-01-01 -e 2024-01-31 -sat Sentinel-2A Sentinel-2B
```

### Python API Usage

```python
from sentinel_revisit_times.sentinel_revisit_calculator import SentinelRevisitCalculator

# Initialize calculator
calculator = SentinelRevisitCalculator(tle_source='celestrak')

# Calculate revisit times for all Sentinel satellites
# (Sentinel-2 satellites automatically filtered to daytime only)
results = calculator.calculate_revisit_for_all_sentinels(
    latitude=40.7128,
    longitude=-74.0060,
    start_date="2024-01-01",
    end_date="2024-01-31",
    minimum_elevation=10.0
)

# Force daytime filtering for all satellites
results_daytime = calculator.calculate_revisit_for_all_sentinels(
    latitude=40.7128,
    longitude=-74.0060,
    start_date="2024-01-01",
    end_date="2024-01-31",
    minimum_elevation=10.0,
    force_daytime_only=True
)

# Include nighttime observations for Sentinel-2
results_nighttime = calculator.calculate_revisit_for_all_sentinels(
    latitude=40.7128,
    longitude=-74.0060,
    start_date="2024-01-01",
    end_date="2024-01-31",
    minimum_elevation=10.0,
    include_nighttime=True
)

# Access results
for satellite_name, stats in results.items():
    print(f"{satellite_name}: {stats['average_revisit_time_days']:.2f} days average")
```

### Running the Example Script

You can also run the provided example script:

```bash
pixi run python sentinel_revisit_times/example_sentinel_revisit.py
```

## Output

### Console Output

The script provides detailed console output including:

- Satellite name and location
- Time period analyzed
- Total number of passes (and daytime passes for filtered satellites)
- Average, median, minimum, and maximum revisit times
- Individual pass times with timestamps
- Daytime filtering information for Sentinel-2 satellites

Example output:
```
================================================================================
SENTINEL SATELLITE REVISIT TIME ANALYSIS
================================================================================

Sentinel-1A
-----------
Location: 40.7128, -74.0060
Time Period: 2024-01-01 to 2024-01-31
Total Passes: 15
Average Revisit Time: 2.07 days
Median Revisit Time: 2.00 days
Min Revisit Time: 1.95 days
Max Revisit Time: 2.20 days

Pass Times (15 total):
   1. 2024-01-01 14:23:45 UTC
   2. 2024-01-03 15:12:30 UTC
   ...

Sentinel-2A
-----------
Location: 40.7128, -74.0060
Time Period: 2024-01-01 to 2024-01-31
Total Passes: 8 (filtered from 12 total passes - daytime only)
Average Revisit Time: 3.25 days
Median Revisit Time: 3.00 days
Min Revisit Time: 2.95 days
Max Revisit Time: 3.50 days

Pass Times (8 total):
   1. 2024-01-01 10:15:30 UTC
   2. 2024-01-04 10:45:12 UTC
   ...
```

### CSV Output

When using the `--output_csv` option, results are saved in CSV format with columns:

- `satellite`: Satellite name
- `location`: Latitude, longitude coordinates
- `time_period`: Analysis time period
- `total_passes`: Number of satellite passes
- `average_revisit_time_days`: Average revisit time in days
- `median_revisit_time_days`: Median revisit time in days
- `min_revisit_time_days`: Minimum revisit time in days
- `max_revisit_time_days`: Maximum revisit time in days

## Satellite Information

### Sentinel-1 Satellites (SAR)
- **Sentinel-1A**: NORAD ID 39634 (launched 2014)
- **Sentinel-1B**: NORAD ID 41456 (launched 2016, retired 2022)
- **Sentinel-1C**: NORAD ID 52860 (launched 2023)
- **Sentinel-1D**: NORAD ID 52861 (launched 2024)

### Sentinel-2 Satellites (Optical)
- **Sentinel-2A**: NORAD ID 40697 (launched 2015)
- **Sentinel-2B**: NORAD ID 42063 (launched 2017)
- **Sentinel-2C**: NORAD ID 43653 (launched 2023)
- **Sentinel-2D**: NORAD ID 43654 (launched 2024)

## Daytime Filtering for Optical Satellites

### Automatic Sentinel-2 Filtering

Sentinel-2 satellites (optical) are automatically filtered to daytime observations only because optical imagery cannot be captured during nighttime. This filtering is based on solar zenith angle calculations:

- **Solar Zenith < 90°**: Daytime condition (sun above horizon)
- **Solar Zenith ≥ 90°**: Nighttime condition (sun below horizon)

### Filtering Behavior

- **Sentinel-1 satellites (SAR)**: No automatic filtering - all passes included
- **Sentinel-2 satellites (optical)**: Automatic daytime filtering applied
- **Override options**: Use `--include_nighttime` to include nighttime passes for Sentinel-2
- **Force filtering**: Use `--daytime_only` to apply daytime filtering to all satellites

### Solar Position Calculations

The script uses precise ephemeris data (DE421) to calculate solar positions and determine solar zenith angles at the target location for each satellite pass time.

## Technical Details

### Revisit Time Calculation

The script calculates revisit time as the time interval between consecutive satellite passes over the target location. Key aspects:

1. **Pass Detection**: Uses Skyfield library to find satellite passes based on TLE data
2. **Elevation Filtering**: Only considers passes above the minimum elevation angle
3. **Culminate Events**: Focuses on the highest point of each pass (culminate events)
4. **Daytime Filtering**: For Sentinel-2, only includes passes with solar zenith < 90°
5. **Statistical Analysis**: Calculates comprehensive statistics from pass intervals

### TLE Data Sources

The script supports multiple sources for TLE (Two-Line Element) data:

1. **Space-Track** (default, recommended):
   - Most accurate and up-to-date TLE data
   - Requires free registration at https://www.space-track.org/
   - Authentication via environment variables (SPACE_TRACK_ID, SPACE_TRACK_PASSWORD)
   - Automatic fallback to Celestrak if authentication fails

2. **Celestrak Active**: 
   - Public TLE data source
   - No authentication required
   - Updated regularly but may be slightly less current than Space-Track
   - Use `--tle_source celestrak_active`

3. **Celestrak Supplemental**: 
   - Alternative Celestrak source
   - May have specialized satellite groups
   - Use `--tle_source celestrak_supplemental`

### Accuracy Considerations

- **TLE Accuracy**: TLE data accuracy decreases over time; fresher data is more accurate
- **Orbital Perturbations**: Real orbits are affected by atmospheric drag and other forces
- **Mission Planning**: Actual acquisition schedules may differ from orbital predictions
- **Cloud Cover**: For optical satellites (Sentinel-2), cloud cover affects data availability
- **Daytime Filtering**: Sentinel-2 results reflect realistic imaging conditions (daytime only)
- **Solar Position**: Solar zenith calculations use precise ephemeris data for accurate daytime determination

## Troubleshooting

### Common Issues

1. **No TLE Data Found**
   - Check internet connection
   - Verify satellite names are correct
   - If using Space-Track:
     - Verify credentials in .env file (SPACE_TRACK_ID and SPACE_TRACK_PASSWORD)
     - Check Space-Track account is active at https://www.space-track.org/
     - Try using Celestrak as fallback: `--tle_source celestrak_active`
   - Try different TLE source

2. **No Passes Found**
   - Increase time period
   - Lower minimum elevation angle
   - Check if location is accessible by satellites

3. **Slow Performance**
   - Reduce time period
   - Analyze fewer satellites
   - Use specific satellite selection

### Error Messages

- `Invalid date format`: Use YYYY-MM-DD format for dates
- `Unknown satellite`: Check satellite name against supported list
- `Failed to fetch TLE data`: Check internet connection and TLE source availability

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## License

This project is open source. Please check the project's license file for details.

## References

- [Skyfield Documentation](https://rhodesmill.org/skyfield/)
- [Space-Track API](https://www.space-track.org/)
- [Celestrak TLE Data](https://celestrak.org/NORAD/elements/)
- [Copernicus Program](https://www.copernicus.eu/)
- [Sentinel Satellites](https://sentinel.esa.int/)
