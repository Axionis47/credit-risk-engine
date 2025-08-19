#!/usr/bin/env python3
"""
Data sanitization script to create safe test data from production.
Masks PII, anonymizes identifiers, and clamps rare categories.
"""

import os
import re
import csv
import json
import hashlib
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

import click

class DataSanitizer:
    def __init__(self):
        self.email_domains = ['example.com', 'test.local', 'sanitized.dev']
        self.fake_names = [
            'Alex Johnson', 'Sam Smith', 'Jordan Brown', 'Casey Davis',
            'Riley Wilson', 'Taylor Anderson', 'Morgan Thomas', 'Avery Jackson'
        ]
        self.video_prefixes = ['VID', 'TEST', 'DEMO', 'SAMPLE']
        
    def hash_identifier(self, value: str, salt: str = "sanitize") -> str:
        """Create consistent hash for identifiers"""
        return hashlib.md5(f"{salt}:{value}".encode()).hexdigest()[:8].upper()
    
    def sanitize_email(self, email: str) -> str:
        """Sanitize email addresses"""
        if not email or '@' not in email:
            return f"user{random.randint(1000, 9999)}@{random.choice(self.email_domains)}"
        
        local_part = email.split('@')[0]
        hashed = self.hash_identifier(local_part)
        domain = random.choice(self.email_domains)
        return f"user{hashed}@{domain}"
    
    def sanitize_name(self, name: str) -> str:
        """Sanitize personal names"""
        if not name:
            return random.choice(self.fake_names)
        
        # Use hash to ensure consistency
        hash_val = int(self.hash_identifier(name), 16) % len(self.fake_names)
        return self.fake_names[hash_val]
    
    def sanitize_video_id(self, video_id: str) -> str:
        """Sanitize video IDs"""
        if not video_id:
            return f"VID{random.randint(1000, 9999)}"
        
        # Keep format but change content
        prefix = random.choice(self.video_prefixes)
        suffix = self.hash_identifier(video_id)[:4]
        return f"{prefix}{suffix}"
    
    def sanitize_text_content(self, text: str) -> str:
        """Sanitize text content while preserving structure"""
        if not text:
            return text
        
        # Remove potential PII patterns
        # Email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
                     lambda m: self.sanitize_email(m.group()), text)
        
        # Phone numbers (simple pattern)
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', 'XXX-XXX-XXXX', text)
        
        # URLs (keep structure but sanitize domain)
        text = re.sub(r'https?://[^\s]+', 'https://example.com/sanitized', text)
        
        # Specific names or brands (you'd customize this)
        sensitive_patterns = [
            (r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', lambda m: self.sanitize_name(m.group())),
        ]
        
        for pattern, replacement in sensitive_patterns:
            text = re.sub(pattern, replacement, text)
        
        return text
    
    def clamp_rare_categories(self, data: List[Dict], category_field: str, min_count: int = 3) -> List[Dict]:
        """Clamp rare categories to protect privacy"""
        # Count occurrences
        category_counts = {}
        for item in data:
            category = item.get(category_field, 'unknown')
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Identify rare categories
        rare_categories = {cat for cat, count in category_counts.items() if count < min_count}
        
        # Replace rare categories
        for item in data:
            if item.get(category_field) in rare_categories:
                item[category_field] = 'other'
        
        return data
    
    def add_noise_to_metrics(self, value: float, noise_factor: float = 0.1) -> float:
        """Add noise to numeric metrics to prevent exact matching"""
        if value == 0:
            return 0
        
        noise = random.uniform(-noise_factor, noise_factor)
        return max(0, value * (1 + noise))
    
    def sanitize_csv_file(self, input_path: str, output_path: str, config: Dict[str, Any]) -> bool:
        """Sanitize a CSV file based on configuration"""
        try:
            with open(input_path, 'r', newline='', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                rows = list(reader)
            
            # Apply sanitization rules
            for row in rows:
                for field, rule in config.get('field_rules', {}).items():
                    if field in row:
                        if rule == 'email':
                            row[field] = self.sanitize_email(row[field])
                        elif rule == 'name':
                            row[field] = self.sanitize_name(row[field])
                        elif rule == 'video_id':
                            row[field] = self.sanitize_video_id(row[field])
                        elif rule == 'text':
                            row[field] = self.sanitize_text_content(row[field])
                        elif rule == 'numeric_noise':
                            try:
                                row[field] = str(self.add_noise_to_metrics(float(row[field])))
                            except (ValueError, TypeError):
                                pass
                        elif rule == 'hash':
                            row[field] = self.hash_identifier(row[field])
            
            # Apply category clamping
            if config.get('clamp_categories'):
                for field, min_count in config['clamp_categories'].items():
                    rows = self.clamp_rare_categories(rows, field, min_count)
            
            # Write sanitized data
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
                if rows:
                    writer = csv.DictWriter(outfile, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
            
            click.echo(f"Sanitized {len(rows)} rows: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            click.echo(f"Error sanitizing {input_path}: {e}")
            return False

@click.command()
@click.option('--input-dir', '-i', default='seeds/prod', help='Input directory with production data')
@click.option('--output-dir', '-o', default='seeds/test', help='Output directory for sanitized data')
@click.option('--config', '-c', default='config/sanitization.json', help='Sanitization configuration file')
def sanitize(input_dir: str, output_dir: str, config: str):
    """Sanitize production data for test environment"""
    
    # Default sanitization config
    default_config = {
        'transcripts': {
            'field_rules': {
                'video_id': 'video_id',
                'transcript': 'text'
            }
        },
        'metrics': {
            'field_rules': {
                'video_id': 'video_id',
                'views': 'numeric_noise',
                'likes': 'numeric_noise',
                'comments': 'numeric_noise',
                'shares': 'numeric_noise',
                'watch_time_seconds': 'numeric_noise'
            },
            'clamp_categories': {
                'category': 3
            }
        },
        'users': {
            'field_rules': {
                'email': 'email',
                'name': 'name',
                'user_id': 'hash'
            }
        }
    }
    
    # Load config if exists
    sanitization_config = default_config
    if os.path.exists(config):
        with open(config) as f:
            sanitization_config = json.load(f)
    else:
        # Create default config file
        os.makedirs(os.path.dirname(config), exist_ok=True)
        with open(config, 'w') as f:
            json.dump(default_config, f, indent=2)
        click.echo(f"Created default sanitization config: {config}")
    
    sanitizer = DataSanitizer()
    
    # Process all CSV files in input directory
    input_path = Path(input_dir)
    if not input_path.exists():
        click.echo(f"Input directory not found: {input_dir}")
        return
    
    success_count = 0
    total_count = 0
    
    for csv_file in input_path.glob('*.csv'):
        total_count += 1
        
        # Determine config based on filename
        file_config = {}
        for key, cfg in sanitization_config.items():
            if key in csv_file.stem.lower():
                file_config = cfg
                break
        
        if not file_config:
            click.echo(f"No sanitization config found for {csv_file.name}, using default")
            file_config = {'field_rules': {}}
        
        # Sanitize file
        output_file = Path(output_dir) / csv_file.name
        if sanitizer.sanitize_csv_file(str(csv_file), str(output_file), file_config):
            success_count += 1
    
    click.echo(f"\nSanitization complete: {success_count}/{total_count} files processed")
    
    if success_count > 0:
        click.echo(f"Sanitized data written to: {output_dir}")
        click.echo("\n⚠️  IMPORTANT: Verify sanitized data before using in test environment")
        click.echo("⚠️  Do not use this data in production!")

if __name__ == '__main__':
    sanitize()
