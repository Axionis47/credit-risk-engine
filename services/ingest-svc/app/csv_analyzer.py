import pandas as pd
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import json

@dataclass
class ColumnMapping:
    video_id: str
    # Metrics columns
    views: Optional[str] = None
    ctr: Optional[str] = None
    avg_view_duration_s: Optional[str] = None
    retention_30s: Optional[str] = None
    published_at: Optional[str] = None
    asof_date: Optional[str] = None
    # Transcripts columns
    transcript: Optional[str] = None

@dataclass
class FileAnalysis:
    role: str  # 'metrics' or 'transcripts'
    columns: ColumnMapping
    row_count: int
    sample_rows: List[Dict[str, Any]]

class CSVAnalyzer:
    """Auto-analyzes CSV files to detect roles and column mappings"""
    
    def __init__(self):
        # Heuristics for detecting column roles
        self.metrics_indicators = {
            'video_id': ['video_id', 'videoid', 'id', 'video'],
            'views': ['view_count', 'views', 'view', 'total_views'],
            'ctr': ['ctr', 'click_through_rate', 'clickthrough', 'click_rate'],
            'avg_view_duration_s': ['avg_view_duration_s', 'avg_view_sec', 'avg_duration', 'watch_time_min', 'avg_view_pct'],
            'retention_30s': ['retention_30s', 'retention', '30s_retention', 'retention_rate'],
            'published_at': ['published_at', 'snippet_published_at', 'publish_date', 'date_published'],
            'asof_date': ['asof_date', 'as_of_date', 'date', 'timestamp']
        }
        
        self.transcripts_indicators = {
            'video_id': ['video_id', 'videoid', 'id', 'video'],
            'transcript': ['transcript', 'body', 'text', 'content', 'script']
        }
    
    def analyze_files(self, metrics_file_path: str, transcripts_file_path: str, 
                     force_override: Optional[Dict[str, str]] = None) -> Tuple[FileAnalysis, FileAnalysis, datetime, datetime]:
        """
        Analyze both CSV files and return analysis results
        
        Returns:
            Tuple of (metrics_analysis, transcripts_analysis, dataset_last_date, embed_cutoff)
        """
        # Read CSV files
        metrics_df = pd.read_csv(metrics_file_path)
        transcripts_df = pd.read_csv(transcripts_file_path)
        
        # Auto-detect roles or use override
        if force_override:
            metrics_role = force_override.get(metrics_file_path.split('/')[-1], 'metrics')
            transcripts_role = force_override.get(transcripts_file_path.split('/')[-1], 'transcripts')
        else:
            metrics_role = self._detect_role(metrics_df)
            transcripts_role = self._detect_role(transcripts_df)
            
            # Ensure we have one of each
            if metrics_role == transcripts_role:
                # Fallback to filename heuristics
                if 'metric' in metrics_file_path.lower():
                    metrics_role = 'metrics'
                    transcripts_role = 'transcripts'
                elif 'transcript' in transcripts_file_path.lower():
                    metrics_role = 'metrics'
                    transcripts_role = 'transcripts'
                else:
                    raise ValueError("Ambiguous CSV roles - please provide force_override")
        
        # Analyze each file
        if metrics_role == 'metrics':
            metrics_analysis = self._analyze_metrics_file(metrics_df)
            transcripts_analysis = self._analyze_transcripts_file(transcripts_df)
        else:
            metrics_analysis = self._analyze_transcripts_file(metrics_df)
            transcripts_analysis = self._analyze_metrics_file(transcripts_df)
        
        # Calculate dataset dates
        dataset_last_date, embed_cutoff = self._calculate_dataset_dates(
            metrics_df if metrics_role == 'metrics' else transcripts_df,
            metrics_analysis.columns if metrics_role == 'metrics' else transcripts_analysis.columns
        )
        
        return metrics_analysis, transcripts_analysis, dataset_last_date, embed_cutoff
    
    def _detect_role(self, df: pd.DataFrame) -> str:
        """Detect if CSV is metrics or transcripts based on column names"""
        columns = [col.lower() for col in df.columns]
        
        metrics_score = 0
        transcripts_score = 0
        
        # Score based on column indicators
        for col in columns:
            if any(indicator in col for indicator in ['view', 'ctr', 'retention', 'metric']):
                metrics_score += 1
            if any(indicator in col for indicator in ['transcript', 'body', 'text', 'content', 'script']):
                transcripts_score += 1
        
        return 'metrics' if metrics_score > transcripts_score else 'transcripts'
    
    def _analyze_metrics_file(self, df: pd.DataFrame) -> FileAnalysis:
        """Analyze metrics CSV file"""
        columns = self._map_columns(df.columns, self.metrics_indicators)
        
        return FileAnalysis(
            role='metrics',
            columns=ColumnMapping(**columns),
            row_count=len(df),
            sample_rows=df.head(5).to_dict('records')
        )
    
    def _analyze_transcripts_file(self, df: pd.DataFrame) -> FileAnalysis:
        """Analyze transcripts CSV file"""
        columns = self._map_columns(df.columns, self.transcripts_indicators)
        
        return FileAnalysis(
            role='transcripts',
            columns=ColumnMapping(**columns),
            row_count=len(df),
            sample_rows=df.head(5).to_dict('records')
        )
    
    def _map_columns(self, df_columns: List[str], indicators: Dict[str, List[str]]) -> Dict[str, Optional[str]]:
        """Map DataFrame columns to expected column names"""
        mapping = {}
        df_columns_lower = [col.lower() for col in df_columns]
        
        for field, possible_names in indicators.items():
            mapping[field] = None
            for possible_name in possible_names:
                for i, col in enumerate(df_columns_lower):
                    if possible_name in col or col in possible_name:
                        mapping[field] = df_columns[i]
                        break
                if mapping[field]:
                    break
        
        return mapping
    
    def _calculate_dataset_dates(self, metrics_df: pd.DataFrame, columns: ColumnMapping) -> Tuple[datetime, datetime]:
        """Calculate dataset_last_date and embed_cutoff (14 days prior)"""
        dates = []
        
        # Collect all dates from published_at and asof_date columns
        if columns.published_at and columns.published_at in metrics_df.columns:
            published_dates = pd.to_datetime(metrics_df[columns.published_at], errors='coerce').dropna()
            dates.extend(published_dates.tolist())
        
        if columns.asof_date and columns.asof_date in metrics_df.columns:
            asof_dates = pd.to_datetime(metrics_df[columns.asof_date], errors='coerce').dropna()
            dates.extend(asof_dates.tolist())
        
        if not dates:
            # Fallback to current date if no dates found
            dataset_last_date = datetime.utcnow()
        else:
            dataset_last_date = max(dates)
        
        # 14-day cutoff for embeddings
        embed_cutoff = dataset_last_date - timedelta(days=14)
        
        return dataset_last_date, embed_cutoff
