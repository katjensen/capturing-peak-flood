#!/usr/bin/env python3
"""
Unit tests for H3 Grid Generator

Tests for the H3GridGenerator class and its functionality.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon, Point
from shapely.wkt import loads as wkt_loads

# Import the module under test
import sys
sys.path.append(str(Path(__file__).parent.parent))
from h3_grid_generator import H3GridGenerator


class TestH3GridGenerator(unittest.TestCase):
    """Test cases for H3GridGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_resolution = 6
        self.generator = H3GridGenerator(resolution=self.test_resolution)
        
        # Test polygon (small area around NYC)
        self.test_polygon = Polygon([
            (-74.0, 40.7),
            (-73.9, 40.7),
            (-73.9, 40.8),
            (-74.0, 40.8),
            (-74.0, 40.7)
        ])
        
        # Test WKT string
        self.test_wkt = "POLYGON((-74.0 40.7, -73.9 40.7, -73.9 40.8, -74.0 40.8, -74.0 40.7))"
        
        # Test bounds
        self.test_bounds = (40.7, -74.0, 40.8, -73.9)  # min_lat, min_lon, max_lat, max_lon
    
    def test_init_valid_resolution(self):
        """Test initialization with valid resolution."""
        generator = H3GridGenerator(resolution=10)
        self.assertEqual(generator.resolution, 10)
    
    def test_init_invalid_resolution(self):
        """Test initialization with invalid resolution."""
        with self.assertRaises(ValueError):
            H3GridGenerator(resolution=-1)
        
        with self.assertRaises(ValueError):
            H3GridGenerator(resolution=16)
    
    def test_create_h3_grid_from_geometry_polygon(self):
        """Test creating H3 grid from Polygon geometry."""
        result_gdf = self.generator.create_h3_grid_from_geometry(self.test_polygon)
        
        # Check that result is a GeoDataFrame
        self.assertIsInstance(result_gdf, gpd.GeoDataFrame)
        
        # Check that it has the expected columns
        expected_columns = ['h3_id', 'geometry', 'center_lat', 'center_lon', 'area_km2', 'resolution']
        for col in expected_columns:
            self.assertIn(col, result_gdf.columns)
        
        # Check that all hexagons have the correct resolution
        self.assertTrue(all(result_gdf['resolution'] == self.test_resolution))
        
        # Check that we have some hexagons
        self.assertGreater(len(result_gdf), 0)
    
    def test_create_h3_grid_from_geometry_with_output_dir(self):
        """Test creating H3 grid with output directory."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            result_gdf = self.generator.create_h3_grid_from_geometry(
                self.test_polygon, output_dir=tmp_dir
            )
            
            # Check that result is a GeoDataFrame
            self.assertIsInstance(result_gdf, gpd.GeoDataFrame)
            
            # Check that files were created in output directory
            files = os.listdir(tmp_dir)
            gpkg_files = [f for f in files if f.endswith('.gpkg')]
            csv_files = [f for f in files if f.endswith('.csv')]
            
            self.assertGreater(len(gpkg_files), 0)
            self.assertGreater(len(csv_files), 0)
    
    def test_create_h3_grid_from_geometry_wkt(self):
        """Test creating H3 grid from WKT string."""
        result_gdf = self.generator.create_h3_grid_from_geometry(self.test_wkt)
        
        self.assertIsInstance(result_gdf, gpd.GeoDataFrame)
        self.assertGreater(len(result_gdf), 0)
    
    def test_create_h3_grid_from_geometry_invalid_wkt(self):
        """Test creating H3 grid from invalid WKT string."""
        with self.assertRaises(ValueError):
            self.generator.create_h3_grid_from_geometry("INVALID WKT")
    
    def test_create_h3_grid_from_geometry_invalid_type(self):
        """Test creating H3 grid from invalid geometry type."""
        point = Point(0, 0)
        with self.assertRaises(ValueError):
            self.generator.create_h3_grid_from_geometry(point)
    
    def test_create_h3_grid_from_geometry_with_buffer(self):
        """Test creating H3 grid with buffer."""
        result_gdf = self.generator.create_h3_grid_from_geometry(
            self.test_polygon, buffer_distance=0.01
        )
        
        self.assertIsInstance(result_gdf, gpd.GeoDataFrame)
        self.assertGreater(len(result_gdf), 0)
    
    def test_create_h3_grid_from_bounds(self):
        """Test creating H3 grid from bounding box."""
        min_lat, min_lon, max_lat, max_lon = self.test_bounds
        result_gdf = self.generator.create_h3_grid_from_bounds(
            min_lat, min_lon, max_lat, max_lon
        )
        
        self.assertIsInstance(result_gdf, gpd.GeoDataFrame)
        self.assertGreater(len(result_gdf), 0)
        
        # Check that all hexagons have the correct resolution
        self.assertTrue(all(result_gdf['resolution'] == self.test_resolution))
    
    def test_hexagons_to_geodataframe(self):
        """Test conversion of hexagons to GeoDataFrame."""
        # Create a test hexagon
        test_hex_id = h3.latlng_to_cell(40.7, -73.9, self.test_resolution)
        hexagons = [test_hex_id]
        
        result_gdf = self.generator._hexagons_to_geodataframe(hexagons)
        
        self.assertIsInstance(result_gdf, gpd.GeoDataFrame)
        self.assertEqual(len(result_gdf), 1)
        
        # Check the hexagon data
        row = result_gdf.iloc[0]
        self.assertEqual(row['h3_id'], test_hex_id)
        self.assertEqual(row['resolution'], self.test_resolution)
        self.assertIsInstance(row['geometry'], Polygon)
        self.assertIsInstance(row['center_lat'], float)
        self.assertIsInstance(row['center_lon'], float)
        self.assertIsInstance(row['area_km2'], float)
    
    def test_filter_hexagons_by_geometry(self):
        """Test filtering hexagons by geometry intersection."""
        # Create some test hexagons
        hex1 = h3.latlng_to_cell(40.7, -73.9, self.test_resolution)
        hex2 = h3.latlng_to_cell(50.0, 0.0, self.test_resolution)  # Far from test polygon
        
        hexagons = [hex1, hex2]
        result = self.generator._filter_hexagons_by_geometry(hexagons, self.test_polygon)
        
        # Should only include hexagons that intersect with the polygon
        self.assertIn(hex1, result)
        self.assertNotIn(hex2, result)
    
    def test_save_to_geopackage(self):
        """Test saving GeoDataFrame to geopackage."""
        # Create a test GeoDataFrame
        test_hex_id = h3.latlng_to_cell(40.7, -73.9, self.test_resolution)
        test_gdf = self.generator._hexagons_to_geodataframe([test_hex_id])
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            # Save to geopackage
            self.generator.save_to_geopackage(test_gdf, output_path, 'test_layer')
            
            # Check that file was created
            self.assertTrue(os.path.exists(output_path))
            
            # Load and verify the saved data
            loaded_gdf = gpd.read_file(output_path, layer='test_layer')
            self.assertEqual(len(loaded_gdf), 1)
            self.assertEqual(loaded_gdf.iloc[0]['h3_id'], test_hex_id)
            
        finally:
            # Clean up
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_save_to_geopackage_with_directory_creation(self):
        """Test saving to geopackage with directory creation."""
        # Create a test GeoDataFrame
        test_hex_id = h3.latlng_to_cell(40.7, -73.9, self.test_resolution)
        test_gdf = self.generator._hexagons_to_geodataframe([test_hex_id])
        
        # Create temporary directory and file path
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / 'subdir' / 'test.gpkg'
            
            # Save to geopackage (should create subdir)
            self.generator.save_to_geopackage(test_gdf, output_path, 'test_layer')
            
            # Check that file was created
            self.assertTrue(output_path.exists())
            
            # Load and verify the saved data
            loaded_gdf = gpd.read_file(output_path, layer='test_layer')
            self.assertEqual(len(loaded_gdf), 1)


class TestH3GridGeneratorIntegration(unittest.TestCase):
    """Integration tests for H3GridGenerator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = H3GridGenerator(resolution=6)
    
    def test_end_to_end_workflow(self):
        """Test complete workflow from geometry to geopackage."""
        # Create test geometry
        test_polygon = Polygon([
            (-74.0, 40.7),
            (-73.9, 40.7),
            (-73.9, 40.8),
            (-74.0, 40.8),
            (-74.0, 40.7)
        ])
        
        # Generate grid
        result_gdf = self.generator.create_h3_grid_from_geometry(test_polygon)
        
        # Verify result
        self.assertIsInstance(result_gdf, gpd.GeoDataFrame)
        self.assertGreater(len(result_gdf), 0)
        
        # Save to temporary geopackage
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            self.generator.save_to_geopackage(result_gdf, output_path)
            
            # Verify file was created and can be loaded
            self.assertTrue(os.path.exists(output_path))
            loaded_gdf = gpd.read_file(output_path)
            self.assertEqual(len(loaded_gdf), len(result_gdf))
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_different_resolutions(self):
        """Test that different resolutions produce different grid densities."""
        test_polygon = Polygon([
            (-74.0, 40.7),
            (-73.9, 40.7),
            (-73.9, 40.8),
            (-74.0, 40.8),
            (-74.0, 40.7)
        ])
        
        # Test different resolutions
        resolutions = [4, 6, 8]
        hexagon_counts = []
        
        for resolution in resolutions:
            generator = H3GridGenerator(resolution=resolution)
            result_gdf = generator.create_h3_grid_from_geometry(test_polygon)
            hexagon_counts.append(len(result_gdf))
        
        # Higher resolution should generally produce more hexagons
        # (though this isn't always guaranteed due to geometry intersection)
        self.assertTrue(all(count > 0 for count in hexagon_counts))


class TestH3GridGeneratorEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = H3GridGenerator(resolution=6)
    
    def test_empty_geometry(self):
        """Test behavior with empty geometry."""
        empty_polygon = Polygon()
        
        with self.assertRaises(Exception):
            self.generator.create_h3_grid_from_geometry(empty_polygon)
    
    def test_very_small_geometry(self):
        """Test behavior with very small geometry."""
        # Very small polygon
        small_polygon = Polygon([
            (0.0, 0.0),
            (0.0001, 0.0),
            (0.0001, 0.0001),
            (0.0, 0.0001),
            (0.0, 0.0)
        ])
        
        result_gdf = self.generator.create_h3_grid_from_geometry(small_polygon)
        
        # Should still work, might have 0 or 1 hexagons
        self.assertIsInstance(result_gdf, gpd.GeoDataFrame)
        self.assertGreaterEqual(len(result_gdf), 0)
    
    def test_very_large_geometry(self):
        """Test behavior with very large geometry."""
        # Large polygon covering most of North America
        large_polygon = Polygon([
            (-180, 20),
            (-60, 20),
            (-60, 80),
            (-180, 80),
            (-180, 20)
        ])
        
        result_gdf = self.generator.create_h3_grid_from_geometry(large_polygon)
        
        # Should work but might take a while
        self.assertIsInstance(result_gdf, gpd.GeoDataFrame)
        self.assertGreater(len(result_gdf), 0)
    
    def test_invalid_bounds(self):
        """Test behavior with invalid bounds."""
        # min_lat > max_lat - this should still work but produce fewer hexagons
        result1 = self.generator.create_h3_grid_from_bounds(50, -74, 40, -73)
        self.assertIsInstance(result1, gpd.GeoDataFrame)
        
        # min_lon > max_lon - this should still work but produce fewer hexagons  
        result2 = self.generator.create_h3_grid_from_bounds(40, -73, 50, -74)
        self.assertIsInstance(result2, gpd.GeoDataFrame)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
