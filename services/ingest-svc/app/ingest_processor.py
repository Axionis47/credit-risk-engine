import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
import json
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Script, PerformanceMetrics
from app.csv_analyzer import CSVAnalyzer, FileAnalysis
from app.text_cleaner import TextCleaner
from app.video_id_validator import VideoIdValidator
from app.config import settings

@dataclass
class IngestReport:
    total_processed: int = 0
    successful: int = 0
    buckets: Dict[str, int] = None
    embeddings_created: int = 0
    processing_time_seconds: float = 0.0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.buckets is None:
            self.buckets = {
                'metrics_only': 0,
                'transcripts_only': 0,
                'invalid_video_id': 0,
                'too_long': 0,
                'too_fresh': 0,
                'unknown_age': 0
            }
        if self.errors is None:
            self.errors = []

class IngestProcessor:
    """Processes CSV files and ingests data into database"""
    
    def __init__(self):
        self.analyzer = CSVAnalyzer()
        self.cleaner = TextCleaner(settings.words_per_minute)
        self.validator = VideoIdValidator()

    def _convert_numpy_types(self, obj):
        """Convert numpy types to native Python types for JSON serialization"""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            # Handle NaN and infinity values
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif obj is None or (isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj))):
            return None
        else:
            return obj
    
    async def process_files(self, metrics_file_path: str, transcripts_file_path: str,
                          db: AsyncSession, force_override: Optional[Dict[str, str]] = None) -> Tuple[Dict, Dict]:
        """
        Process CSV files and ingest data
        
        Returns:
            Tuple of (ingest_plan, ingest_report)
        """
        start_time = datetime.utcnow()
        
        # Analyze files
        metrics_analysis, transcripts_analysis, dataset_last_date, embed_cutoff = \
            self.analyzer.analyze_files(metrics_file_path, transcripts_file_path, force_override)
        
        # Create ingest plan
        ingest_plan = {
            'metrics_file': asdict(metrics_analysis),
            'transcripts_file': asdict(transcripts_analysis),
            'dataset_last_date': dataset_last_date.isoformat(),
            'embed_cutoff': embed_cutoff.isoformat(),
            'estimated_processing_time_minutes': self._estimate_processing_time(
                metrics_analysis.row_count + transcripts_analysis.row_count
            )
        }
        
        # Process data
        report = await self._process_data(
            metrics_file_path, transcripts_file_path,
            metrics_analysis, transcripts_analysis,
            embed_cutoff, db
        )
        
        # Calculate processing time
        end_time = datetime.utcnow()
        report.processing_time_seconds = (end_time - start_time).total_seconds()
        
        # Convert numpy types to native Python types for JSON serialization
        ingest_plan = self._convert_numpy_types(ingest_plan)
        report_dict = self._convert_numpy_types(asdict(report))
        return ingest_plan, report_dict
    
    async def _process_data(self, metrics_file_path: str, transcripts_file_path: str,
                          metrics_analysis: FileAnalysis, transcripts_analysis: FileAnalysis,
                          embed_cutoff: datetime, db: AsyncSession) -> IngestReport:
        """Process and ingest the actual data"""
        report = IngestReport()
        
        # Load CSV files
        metrics_df = pd.read_csv(metrics_file_path)
        transcripts_df = pd.read_csv(transcripts_file_path)
        
        # Normalize video IDs
        metrics_df = self._normalize_video_ids(metrics_df, metrics_analysis.columns.video_id, report)
        transcripts_df = self._normalize_video_ids(transcripts_df, transcripts_analysis.columns.video_id, report)
        
        # Find intersection
        metrics_video_ids = set(metrics_df[metrics_analysis.columns.video_id].dropna())
        transcripts_video_ids = set(transcripts_df[transcripts_analysis.columns.video_id].dropna())
        
        intersection_ids = metrics_video_ids & transcripts_video_ids
        
        # Update buckets
        report.buckets['metrics_only'] = len(metrics_video_ids - intersection_ids)
        report.buckets['transcripts_only'] = len(transcripts_video_ids - intersection_ids)
        
        # Process intersection
        for video_id in intersection_ids:
            try:
                # Process each video in its own transaction to prevent rollback cascade
                async with db.begin():
                    await self._process_video(
                        video_id, metrics_df, transcripts_df,
                        metrics_analysis, transcripts_analysis,
                        embed_cutoff, db, report
                    )
                    report.total_processed += 1
            except Exception as e:
                # Log the error but continue processing other videos
                error_msg = f"Error processing {video_id}: {str(e)}"
                report.errors.append(error_msg)
                print(f"⚠️ {error_msg}")  # Also log to console for debugging
                # Rollback is automatic when exiting the transaction context
        
        await db.commit()
        return report
    
    def _normalize_video_ids(self, df: pd.DataFrame, video_id_col: str, report: IngestReport) -> pd.DataFrame:
        """Normalize video IDs and filter invalid ones"""
        if video_id_col not in df.columns:
            return df
        
        # Normalize video IDs
        df[video_id_col] = df[video_id_col].apply(self.validator.normalize_video_id)
        
        # Count invalid IDs
        invalid_count = df[video_id_col].isna().sum()
        report.buckets['invalid_video_id'] += invalid_count
        
        # Filter out invalid IDs
        return df.dropna(subset=[video_id_col])
    
    async def _process_video(self, video_id: str, metrics_df: pd.DataFrame, transcripts_df: pd.DataFrame,
                           metrics_analysis: FileAnalysis, transcripts_analysis: FileAnalysis,
                           embed_cutoff: datetime, db: AsyncSession, report: IngestReport):
        """Process a single video's data"""
        
        # Get metrics data
        metrics_row = metrics_df[metrics_df[metrics_analysis.columns.video_id] == video_id].iloc[0]
        
        # Get transcript data
        transcript_row = transcripts_df[transcripts_df[transcripts_analysis.columns.video_id] == video_id].iloc[0]
        
        # Clean transcript
        raw_transcript = transcript_row[transcripts_analysis.columns.transcript]
        cleaned_body, duration_seconds = self.cleaner.clean_transcript(raw_transcript)
        
        # Check duration limit
        if duration_seconds > settings.max_ref_duration_seconds:
            report.buckets['too_long'] += 1
            return
        
        # Parse dates for age check
        published_at = self._parse_date(metrics_row, metrics_analysis.columns.published_at)
        asof_date = self._parse_date(metrics_row, metrics_analysis.columns.asof_date)
        
        # Determine if eligible for embedding
        eligible_for_embedding = False
        if published_at:
            eligible_for_embedding = published_at <= embed_cutoff
        elif asof_date:
            # Use earliest asof_date for this video_id if no published_at
            eligible_for_embedding = asof_date <= embed_cutoff
        else:
            report.buckets['unknown_age'] += 1
            return
        
        if not eligible_for_embedding:
            report.buckets['too_fresh'] += 1
        
        # Check if script already exists for this video_id and version
        # Note: Using the actual database schema (content instead of body, no source column)
        existing_script = await db.execute(
            select(Script).where(
                Script.video_id == video_id,
                Script.version == 0
            )
        )
        existing_script = existing_script.scalar_one_or_none()

        if existing_script:
            # Update existing script
            existing_script.body = cleaned_body  # This maps to 'content' in the actual DB
            existing_script.duration_seconds = duration_seconds
            existing_script.updated_at = datetime.utcnow()
            db.add(existing_script)
        else:
            # Insert new script
            script_data = {
                'video_id': video_id,
                'version': 0,
                'body': cleaned_body,  # This maps to 'content' in the actual DB
                'duration_seconds': duration_seconds,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            new_script = Script(**script_data)
            db.add(new_script)
        
        # Insert performance metrics
        metrics_data = {
            'video_id': video_id,
            'views': int(metrics_row.get(metrics_analysis.columns.views, 0)),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        # Add optional metrics (only those that exist in the database schema)
        if metrics_analysis.columns.retention_30s and metrics_analysis.columns.retention_30s in metrics_row:
            metrics_data['retention_30s'] = float(metrics_row[metrics_analysis.columns.retention_30s])
        
        if published_at:
            metrics_data['published_at'] = published_at
        
        if asof_date:
            metrics_data['asof_date'] = asof_date
        
        # Check if performance metrics already exist for this video_id
        existing_metrics = await db.execute(
            select(PerformanceMetrics).where(PerformanceMetrics.video_id == video_id)
        )
        existing_metrics = existing_metrics.scalar_one_or_none()

        if existing_metrics:
            # Update existing metrics
            for key, value in metrics_data.items():
                if key not in ['video_id', 'created_at']:  # Don't update these fields
                    setattr(existing_metrics, key, value)
            db.add(existing_metrics)
        else:
            # Insert new metrics
            new_metrics = PerformanceMetrics(**metrics_data)
            db.add(new_metrics)
        
        # Note: Embedding creation will be handled by embed-svc
        if eligible_for_embedding:
            report.embeddings_created += 1
        
        report.successful += 1
    
    def _parse_date(self, row: pd.Series, date_col: Optional[str]) -> Optional[datetime]:
        """Parse date from row"""
        if not date_col or date_col not in row or pd.isna(row[date_col]):
            return None
        
        try:
            return pd.to_datetime(row[date_col])
        except:
            return None
    
    def _estimate_processing_time(self, total_rows: int) -> float:
        """Estimate processing time in minutes"""
        # Rough estimate: 1000 rows per minute
        return max(1.0, total_rows / 1000.0)
