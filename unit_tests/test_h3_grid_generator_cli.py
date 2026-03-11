#!/usr/bin/env python3
"""
Unit tests for H3 Grid Generator CLI functionality

Tests for the command-line interface and main function.
"""

import unittest
import tempfile
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import geopandas as gpd
from shapely.geometry import Polygon

# Import the module under test
sys.path.append(str(Path(__file__).parent.parent))
from h3_grid_generator import main


class TestH3GridGeneratorCLI(unittest.TestCase):
    """Test cases for H3GridGenerator CLI functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_polygon = Polygon([
            (-74.0, 40.7),
            (-73.9, 40.7),
            (-73.9, 40.8),
            (-74.0, 40.8),
            (-74.0, 40.7)
        ])
        
        self.test_wkt = "POLYGON((-74.0 40.7, -73.9 40.7, -73.9 40.8, -74.0 40.8, -74.0 40.7))"
    
    def test_cli_with_geometry_wkt(self):
        """Test CLI with WKT geometry."""
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            # Test with WKT geometry
            sys.argv = [
                'h3_grid_generator.py',
                '--geometry', self.test_wkt,
                '--resolution', '6',
                '--output', output_path,
                '--verbose'
            ]
            
            result = main()
            self.assertEqual(result, 0)
            
            # Check that output file was created
            self.assertTrue(os.path.exists(output_path))
            
            # Load and verify the output
            gdf = gpd.read_file(output_path)
            self.assertGreater(len(gdf), 0)
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_cli_with_bounds(self):
        """Test CLI with bounding box."""
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            # Test with bounds
            sys.argv = [
                'h3_grid_generator.py',
                '--bounds', '40.7', '-74.0', '40.8', '-73.9',
                '--resolution', '6',
                '--output', output_path
            ]
            
            result = main()
            self.assertEqual(result, 0)
            
            # Check that output file was created
            self.assertTrue(os.path.exists(output_path))
            
            # Load and verify the output
            gdf = gpd.read_file(output_path)
            self.assertGreater(len(gdf), 0)
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_cli_with_geometry_file(self):
        """Test CLI with geometry file."""
        # Create a temporary GeoJSON file
        with tempfile.NamedTemporaryFile(suffix='.geojson', delete=False) as tmp_file:
            geojson_path = tmp_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            # Create test GeoJSON
            test_gdf = gpd.GeoDataFrame({'id': [1]}, geometry=[self.test_polygon], crs='EPSG:4326')
            test_gdf.to_file(geojson_path, driver='GeoJSON')
            
            # Test with geometry file
            sys.argv = [
                'h3_grid_generator.py',
                '--geometry', geojson_path,
                '--resolution', '6',
                '--output', output_path
            ]
            
            result = main()
            self.assertEqual(result, 0)
            
            # Check that output file was created
            self.assertTrue(os.path.exists(output_path))
            
            # Load and verify the output
            gdf = gpd.read_file(output_path)
            self.assertGreater(len(gdf), 0)
            
        finally:
            if os.path.exists(geojson_path):
                os.unlink(geojson_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_cli_missing_required_args(self):
        """Test CLI with missing required arguments (now optional with output-dir)."""
        # Test missing output - should work now since output-dir is provided by default
        sys.argv = [
            'h3_grid_generator.py',
            '--geometry', self.test_wkt,
            '--resolution', '6'
        ]
        
        result = main()
        self.assertEqual(result, 0)
    
    def test_cli_missing_geometry_or_bounds(self):
        """Test CLI without geometry or bounds."""
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            sys.argv = [
                'h3_grid_generator.py',
                '--resolution', '6',
                '--output', output_path
            ]
            
            result = main()
            self.assertEqual(result, 1)  # Should return error code
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_cli_invalid_resolution(self):
        """Test CLI with invalid resolution."""
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            sys.argv = [
                'h3_grid_generator.py',
                '--geometry', self.test_wkt,
                '--resolution', '20',  # Invalid resolution
                '--output', output_path
            ]
            
            # Should return error code 1 due to ValueError
            result = main()
            self.assertEqual(result, 1)
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_cli_with_buffer(self):
        """Test CLI with buffer option."""
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            sys.argv = [
                'h3_grid_generator.py',
                '--geometry', self.test_wkt,
                '--resolution', '6',
                '--output', output_path,
                '--buffer', '0.01'
            ]
            
            result = main()
            self.assertEqual(result, 0)
            
            # Check that output file was created
            self.assertTrue(os.path.exists(output_path))
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_cli_with_custom_layer_name(self):
        """Test CLI with custom layer name."""
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            sys.argv = [
                'h3_grid_generator.py',
                '--geometry', self.test_wkt,
                '--resolution', '6',
                '--output', output_path,
                '--layer-name', 'custom_layer'
            ]
            
            result = main()
            self.assertEqual(result, 0)
            
            # Check that output file was created
            self.assertTrue(os.path.exists(output_path))
            
            # Load and verify the layer name
            gdf = gpd.read_file(output_path, layer='custom_layer')
            self.assertGreater(len(gdf), 0)
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_cli_with_output_directory(self):
        """Test CLI with output directory."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            sys.argv = [
                'h3_grid_generator.py',
                '--geometry', self.test_wkt,
                '--resolution', '6',
                '--output-dir', tmp_dir
            ]
            
            result = main()
            self.assertEqual(result, 0)
            
            # Check that files were created in output directory
            files = os.listdir(tmp_dir)
            gpkg_files = [f for f in files if f.endswith('.gpkg')]
            csv_files = [f for f in files if f.endswith('.csv')]
            
            self.assertGreater(len(gpkg_files), 0)
            self.assertGreater(len(csv_files), 0)


class TestH3GridGeneratorCLIIntegration(unittest.TestCase):
    """Integration tests for CLI functionality."""
    
    def test_cli_subprocess(self):
        """Test CLI as subprocess."""
        script_path = Path(__file__).parent.parent / 'h3_grid_generator.py'
        
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        try:
            # Run the script as subprocess
            cmd = [
                sys.executable,
                str(script_path),
                '--geometry', 'POLYGON((-74.0 40.7, -73.9 40.7, -73.9 40.8, -74.0 40.8, -74.0 40.7))',
                '--resolution', '6',
                '--output', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Check that it ran successfully
            self.assertEqual(result.returncode, 0)
            
            # Check that output file was created
            self.assertTrue(os.path.exists(output_path))
            
            # Load and verify the output
            gdf = gpd.read_file(output_path)
            self.assertGreater(len(gdf), 0)
            
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
