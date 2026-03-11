#!/usr/bin/env python3
"""
Test runner for H3 Grid Generator unit tests

This script runs all unit tests for the H3 Grid Generator.
"""

import unittest
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the main module
sys.path.append(str(Path(__file__).parent.parent))

# Import test modules
from test_h3_grid_generator import TestH3GridGenerator, TestH3GridGeneratorIntegration, TestH3GridGeneratorEdgeCases
from test_h3_grid_generator_cli import TestH3GridGeneratorCLI, TestH3GridGeneratorCLIIntegration


def run_tests():
    """Run all unit tests."""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestH3GridGenerator))
    test_suite.addTest(unittest.makeSuite(TestH3GridGeneratorIntegration))
    test_suite.addTest(unittest.makeSuite(TestH3GridGeneratorEdgeCases))
    test_suite.addTest(unittest.makeSuite(TestH3GridGeneratorCLI))
    test_suite.addTest(unittest.makeSuite(TestH3GridGeneratorCLIIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)
