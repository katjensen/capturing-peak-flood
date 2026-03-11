#!/usr/bin/env python3
"""
Example usage of H3 Grid Generator

This script demonstrates how to use the H3GridGenerator class programmatically.
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import the main module
sys.path.append(str(Path(__file__).parent.parent))

from h3_grid_generator import H3GridGenerator
from shapely.geometry import Polygon
import geopandas as gpd


def example_basic_usage():
    """Basic usage example."""
    print("=== Basic Usage Example ===")
    
    # Create a generator with resolution 6
    generator = H3GridGenerator(resolution=6)
    
    # Define a test polygon (small area around NYC)
    test_polygon = Polygon([
        (-74.0, 40.7),
        (-73.9, 40.7),
        (-73.9, 40.8),
        (-74.0, 40.8),
        (-74.0, 40.7)
    ])
    
    # Generate H3 grid
    result_gdf = generator.create_h3_grid_from_geometry(test_polygon)
    
    print(f"Generated {len(result_gdf)} hexagons")
    print(f"Resolution: {generator.resolution}")
    print(f"Columns: {list(result_gdf.columns)}")
    print(f"CRS: {result_gdf.crs}")
    
    # Save to geopackage
    output_path = "example_h3_grid.gpkg"
    generator.save_to_geopackage(result_gdf, output_path, "nyc_grid")
    print(f"Saved to: {output_path}")
    
    return result_gdf


def example_with_output_directory():
    """Example using output directory."""
    print("\n=== Output Directory Example ===")
    
    # Create a generator with resolution 6
    generator = H3GridGenerator(resolution=6)
    
    # Define a test polygon
    test_polygon = Polygon([
        (-74.0, 40.7),
        (-73.9, 40.7),
        (-73.9, 40.8),
        (-74.0, 40.8),
        (-74.0, 40.7)
    ])
    
    # Generate H3 grid with automatic output directory saving
    result_gdf = generator.create_h3_grid_from_geometry(
        test_polygon, output_dir="./output/"
    )
    
    print(f"Generated {len(result_gdf)} hexagons")
    print(f"Resolution: {generator.resolution}")
    print("Files automatically saved to ./output/ directory")
    print("Both .gpkg and .csv files were created")
    
    return result_gdf


def example_different_resolutions():
    """Example with different resolutions."""
    print("\n=== Different Resolutions Example ===")
    
    # Test polygon
    test_polygon = Polygon([
        (-74.0, 40.7),
        (-73.9, 40.7),
        (-73.9, 40.8),
        (-74.0, 40.8),
        (-74.0, 40.7)
    ])
    
    resolutions = [4, 6, 8]
    
    for resolution in resolutions:
        generator = H3GridGenerator(resolution=resolution)
        result_gdf = generator.create_h3_grid_from_geometry(test_polygon)
        
        print(f"Resolution {resolution}: {len(result_gdf)} hexagons")
        
        # Save each resolution to separate file
        output_path = f"example_h3_grid_res_{resolution}.gpkg"
        generator.save_to_geopackage(result_gdf, output_path, f"grid_res_{resolution}")


def example_bounds_usage():
    """Example using bounding box."""
    print("\n=== Bounds Usage Example ===")
    
    generator = H3GridGenerator(resolution=6)
    
    # Define bounds (min_lat, min_lon, max_lat, max_lon)
    bounds = (40.7, -74.0, 40.8, -73.9)
    
    # Generate grid from bounds
    result_gdf = generator.create_h3_grid_from_bounds(*bounds)
    
    print(f"Generated {len(result_gdf)} hexagons from bounds")
    print(f"Bounds: {bounds}")
    
    # Save to geopackage
    output_path = "example_h3_grid_bounds.gpkg"
    generator.save_to_geopackage(result_gdf, output_path, "bounds_grid")
    print(f"Saved to: {output_path}")


def example_wkt_usage():
    """Example using WKT geometry."""
    print("\n=== WKT Usage Example ===")
    
    generator = H3GridGenerator(resolution=6)
    
    # Define geometry as WKT string
    wkt_geometry = "POLYGON((-74.0 40.7, -73.9 40.7, -73.9 40.8, -74.0 40.8, -74.0 40.7))"
    
    # Generate grid from WKT
    result_gdf = generator.create_h3_grid_from_geometry(wkt_geometry)
    
    print(f"Generated {len(result_gdf)} hexagons from WKT")
    
    # Save to geopackage
    output_path = "example_h3_grid_wkt.gpkg"
    generator.save_to_geopackage(result_gdf, output_path, "wkt_grid")
    print(f"Saved to: {output_path}")


def example_with_buffer():
    """Example with buffer."""
    print("\n=== Buffer Usage Example ===")
    
    generator = H3GridGenerator(resolution=6)
    
    # Test polygon
    test_polygon = Polygon([
        (-74.0, 40.7),
        (-73.9, 40.7),
        (-73.9, 40.8),
        (-74.0, 40.8),
        (-74.0, 40.7)
    ])
    
    # Generate grid with buffer
    result_gdf = generator.create_h3_grid_from_geometry(test_polygon, buffer_distance=0.01)
    
    print(f"Generated {len(result_gdf)} hexagons with buffer")
    
    # Save to geopackage
    output_path = "example_h3_grid_buffer.gpkg"
    generator.save_to_geopackage(result_gdf, output_path, "buffer_grid")
    print(f"Saved to: {output_path}")


def main():
    """Run all examples."""
    try:
        # Run examples
        example_basic_usage()
        example_with_output_directory()
        example_different_resolutions()
        example_bounds_usage()
        example_wkt_usage()
        example_with_buffer()
        
        print("\n=== All examples completed successfully! ===")
        print("Check the generated .gpkg files in the current directory.")
        print("Check the ./output/ directory for auto-generated files.")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
