#!/usr/bin/env python3
"""
Preflight check script for environment validation and mock data detection.
This script MUST be run at service startup to ensure production safety.
"""

import os
import sys
import re
import yaml
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mock data signature patterns (case-insensitive)
MOCK_SIGNATURES = [
    r'/(^|[\\/])(mocks?|fixtures?|samples?|devdata|seeds)([\\/]|$)/',
    r'/lorem ipsum/',
    r'/example\.com/',
    r'/example@/',
    r'/testuser/',
    r'/^fake_/',
    r'/^dummy_/',
    r'/seed_/',
    r'/demo@example\.com/',
    r'/mock-.*-token/',
    r'/Demo User/',
    r'/sample_data/',
    r'/__mocks__/',
    r'/test_.*\.py$/',
    r'/.*_test\.py$/',
    r'/.*\.test\./',
    r'/.*\.spec\./',
]

class PreflightError(Exception):
    """Critical preflight check failure"""
    pass

class PreflightChecker:
    def __init__(self):
        self.app_env = os.getenv('APP_ENV')
        self.config = None
        self.errors = []
        self.warnings = []
        
    def run_all_checks(self) -> bool:
        """Run all preflight checks. Returns True if all pass."""
        try:
            logger.info("Starting preflight checks...")
            
            # Critical checks - fail immediately
            self.check_app_env()
            self.load_config()
            self.check_environment_resources()
            
            # Production-specific checks
            if self.app_env == 'prod':
                self.check_production_safety()
                self.scan_for_mock_data()
                self.verify_production_resources()
            
            # Report results
            self.report_results()
            
            if self.errors:
                logger.error(f"Preflight checks FAILED with {len(self.errors)} errors")
                return False
                
            logger.info("All preflight checks PASSED")
            return True
            
        except Exception as e:
            logger.error(f"Preflight check crashed: {e}")
            return False
    
    def check_app_env(self):
        """Verify APP_ENV is set and valid"""
        if not self.app_env:
            raise PreflightError("APP_ENV environment variable is required")
            
        valid_envs = {'dev', 'test', 'prod'}
        if self.app_env not in valid_envs:
            raise PreflightError(f"APP_ENV must be one of {valid_envs}, got: {self.app_env}")
            
        logger.info(f"Environment: {self.app_env}")
    
    def load_config(self):
        """Load environment-specific configuration"""
        config_dir = Path(__file__).parent.parent / 'config'
        
        # Load defaults first
        defaults_path = config_dir / 'defaults.yaml'
        if not defaults_path.exists():
            raise PreflightError(f"Default config not found: {defaults_path}")
            
        with open(defaults_path) as f:
            self.config = yaml.safe_load(f)
        
        # Load environment-specific config
        env_config_path = config_dir / f'{self.app_env}.yaml'
        if not env_config_path.exists():
            raise PreflightError(f"Environment config not found: {env_config_path}")
            
        with open(env_config_path) as f:
            env_config = yaml.safe_load(f)
            
        # Merge configs (env overrides defaults)
        self.config.update(env_config)
        
        logger.info(f"Loaded configuration for environment: {self.app_env}")
    
    def check_environment_resources(self):
        """Verify environment-specific resources are correctly configured"""
        if not self.config:
            raise PreflightError("Configuration not loaded")
            
        # Check database configuration
        db_name = self.config.get('database', {}).get('name', '')
        if self.app_env not in db_name:
            self.errors.append(f"Database name '{db_name}' doesn't contain environment '{self.app_env}'")
        
        # Check vector index
        vector_index = self.config.get('vector', {}).get('index_name', '')
        if self.app_env not in vector_index:
            self.errors.append(f"Vector index '{vector_index}' doesn't contain environment '{self.app_env}'")
        
        # Check storage buckets
        gcs_bucket = self.config.get('storage', {}).get('gcs_bucket', '')
        if self.app_env not in gcs_bucket:
            self.errors.append(f"GCS bucket '{gcs_bucket}' doesn't contain environment '{self.app_env}'")
    
    def check_production_safety(self):
        """Production-specific safety checks"""
        if self.app_env != 'prod':
            return
            
        # Verify mock data is disabled
        mock_allowed = self.config.get('features', {}).get('mock_data_allowed', True)
        if mock_allowed:
            raise PreflightError("mock_data_allowed MUST be false in production")
        
        # Verify debug mode is disabled
        debug_mode = self.config.get('features', {}).get('debug_mode', True)
        if debug_mode:
            raise PreflightError("debug_mode MUST be false in production")
        
        # Check log level
        log_level = self.config.get('app', {}).get('log_level', 'DEBUG')
        if log_level in ['DEBUG', 'TRACE']:
            self.warnings.append(f"Log level '{log_level}' may be too verbose for production")
    
    def scan_for_mock_data(self):
        """Scan filesystem and environment for mock data signatures"""
        if self.app_env != 'prod':
            return
            
        logger.info("Scanning for mock data signatures in production...")
        
        # Scan current directory and common paths
        scan_paths = [
            Path.cwd(),
            Path('/app'),  # Common Docker app path
            Path('/opt/app'),  # Alternative app path
        ]
        
        mock_files = []
        for scan_path in scan_paths:
            if scan_path.exists():
                mock_files.extend(self.scan_directory_for_mocks(scan_path))
        
        # Scan environment variables
        mock_env_vars = self.scan_environment_for_mocks()
        
        if mock_files or mock_env_vars:
            error_msg = "Mock data detected in production environment:\n"
            if mock_files:
                error_msg += f"Files: {mock_files}\n"
            if mock_env_vars:
                error_msg += f"Environment variables: {mock_env_vars}\n"
            raise PreflightError(error_msg)
    
    def scan_directory_for_mocks(self, path: Path) -> List[str]:
        """Scan directory for mock data patterns"""
        mock_files = []
        
        # Skip certain directories
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.pytest_cache', 'venv', '.venv'}
        
        try:
            for item in path.rglob('*'):
                if any(skip_dir in item.parts for skip_dir in skip_dirs):
                    continue
                    
                if item.is_file():
                    # Check filename
                    if self.matches_mock_pattern(str(item)):
                        mock_files.append(str(item))
                        continue
                    
                    # Check file content for small files
                    if item.stat().st_size < 1024 * 1024:  # 1MB limit
                        try:
                            content = item.read_text(encoding='utf-8', errors='ignore')
                            if self.matches_mock_pattern(content):
                                mock_files.append(str(item))
                        except (UnicodeDecodeError, PermissionError):
                            pass  # Skip binary or inaccessible files
                            
        except PermissionError:
            logger.warning(f"Permission denied scanning {path}")
            
        return mock_files
    
    def scan_environment_for_mocks(self) -> List[str]:
        """Scan environment variables for mock patterns"""
        mock_env_vars = []
        
        for key, value in os.environ.items():
            if self.matches_mock_pattern(f"{key}={value}"):
                mock_env_vars.append(f"{key}={value}")
                
        return mock_env_vars
    
    def matches_mock_pattern(self, text: str) -> bool:
        """Check if text matches any mock data pattern"""
        text_lower = text.lower()
        
        for pattern in MOCK_SIGNATURES:
            # Remove regex delimiters for simple string matching
            pattern_clean = pattern.strip('/').replace('\\/', '/')
            
            if re.search(pattern_clean, text_lower, re.IGNORECASE):
                return True
                
        return False
    
    def verify_production_resources(self):
        """Verify production resources are accessible and correct"""
        if self.app_env != 'prod':
            return
            
        # This would include checks like:
        # - Database connectivity
        # - Vector store accessibility  
        # - GCS bucket permissions
        # - Secret manager access
        # For now, we'll just verify the configuration points to prod resources
        
        prod_indicators = ['prod', 'production']
        
        # Check database
        db_name = self.config.get('database', {}).get('name', '')
        if not any(indicator in db_name.lower() for indicator in prod_indicators):
            self.warnings.append(f"Database name '{db_name}' doesn't clearly indicate production")
    
    def report_results(self):
        """Report check results"""
        if self.warnings:
            logger.warning(f"Preflight warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        if self.errors:
            logger.error(f"Preflight errors ({len(self.errors)}):")
            for error in self.errors:
                logger.error(f"  - {error}")

def main():
    """Main entry point"""
    checker = PreflightChecker()
    
    if not checker.run_all_checks():
        logger.error("PREFLIGHT CHECKS FAILED - SERVICE STARTUP ABORTED")
        sys.exit(2)  # Exit code 2 for preflight failure
    
    logger.info("PREFLIGHT CHECKS PASSED - SERVICE STARTUP APPROVED")
    sys.exit(0)

if __name__ == '__main__':
    main()
