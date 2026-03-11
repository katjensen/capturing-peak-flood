#!/usr/bin/env python3
"""
Example usage of the Sentinel Revisit Time Calculator

This script demonstrates how to use the SentinelRevisitCalculator class
to calculate revisit times for Sentinel-1 and Sentinel-2 satellites.
"""

from sentinel_revisit_calculator import SentinelRevisitCalculator, format_results, save_results_to_csv


def example_usage():
    """Example usage of the Sentinel Revisit Calculator."""
    
    # Initialize the calculator
    calculator = SentinelRevisitCalculator(tle_source='celestrak')
    
    # Example parameters
    latitude = 40.7128  # New York City
    longitude = -74.0060
    start_date = "2025-06-01" #Jun 1, 2025- Aug 31, 2025
    end_date = "2024-08-31"
    minimum_elevation = 10.0  # degrees
    
    print("Sentinel Revisit Time Calculator - Example Usage")
    print("=" * 50)
    print(f"Location: {latitude}, {longitude}")
    print(f"Time Period: {start_date} to {end_date}")
    print(f"Minimum Elevation: {minimum_elevation}°")
    print()
    
    # Calculate for specific satellites
    satellites_to_analyze = ['Sentinel-1A', 'Sentinel-2A']
    
    results = calculator.calculate_revisit_for_all_sentinels(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        minimum_elevation=minimum_elevation,
        satellites=satellites_to_analyze
    )
    
    # Display results
    print(format_results(results))
    
    # Save to CSV
    save_results_to_csv(results, "sentinel_revisit_example.csv")
    print("\nResults saved to 'sentinel_revisit_example.csv'")


def calculate_for_multiple_locations():
    """Example of calculating revisit times for multiple locations."""
    
    calculator = SentinelRevisitCalculator()
    
    # Multiple locations of interest
    locations = [
        {"name": "New York", "lat": 40.7128, "lon": -74.0060},
        {"name": "London", "lat": 51.5074, "lon": -0.1278},
        {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
        {"name": "Sydney", "lat": -33.8688, "lon": 151.2093},
    ]
    
    start_date = "2024-01-01"
    end_date = "2024-01-31"
    
    print("\n" + "=" * 80)
    print("MULTIPLE LOCATIONS ANALYSIS")
    print("=" * 80)
    
    all_results = {}
    
    for location in locations:
        print(f"\nAnalyzing {location['name']} ({location['lat']}, {location['lon']})...")
        
        results = calculator.calculate_revisit_for_all_sentinels(
            latitude=location['lat'],
            longitude=location['lon'],
            start_date=start_date,
            end_date=end_date,
            satellites=['Sentinel-1A', 'Sentinel-2A']  # Just analyze these two for speed
        )
        
        # Add location name to results
        for satellite, stats in results.items():
            stats['location_name'] = location['name']
        
        all_results.update(results)
    
    # Display summary
    print("\nSUMMARY BY SATELLITE:")
    print("-" * 40)
    
    satellites = set()
    for key in all_results.keys():
        satellite = key.split('_')[0] if '_' in key else key
        satellites.add(satellite)
    
    for satellite in sorted(satellites):
        print(f"\n{satellite}:")
        satellite_results = {k: v for k, v in all_results.items() if satellite in k}
        
        for key, stats in satellite_results.items():
            location_name = stats.get('location_name', 'Unknown')
            avg_revisit = stats.get('average_revisit_time_days')
            total_passes = stats.get('total_passes', 0)
            
            if avg_revisit is not None:
                print(f"  {location_name}: {avg_revisit:.2f} days avg ({total_passes} passes)")
            else:
                print(f"  {location_name}: No data ({total_passes} passes)")


if __name__ == "__main__":
    # Run the basic example
    example_usage()
    
    # Uncomment the line below to run the multiple locations example
    # calculate_for_multiple_locations()
