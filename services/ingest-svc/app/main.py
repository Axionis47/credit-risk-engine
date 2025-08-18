import os
import tempfile
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict
import structlog
import uvicorn

from app.config import settings
from app.database import get_db, init_db
from app.ingest_processor import IngestProcessor
from app.gcs_client import GCSClient

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(
    title="Ingest Service",
    description="CSV analysis and data ingestion service",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global processor instance
processor = IngestProcessor()

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    await init_db()
    logger.info("Ingest service started", port=settings.port)

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2024-12-01T00:00:00Z",
        "service": "ingest-svc",
        "version": "1.0.0"
    }

@app.post("/api/ingest/auto")
async def auto_ingest(
    metrics_file: UploadFile = File(...),
    transcripts_file: UploadFile = File(...),
    force_role_override: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Auto-analyze and ingest CSV files
    
    Args:
        metrics_file: CSV file with performance metrics
        transcripts_file: CSV file with video transcripts
        force_role_override: JSON string with role overrides (optional)
        
    Returns:
        Ingest plan and report
    """
    logger.info("Starting auto ingest", 
                metrics_filename=metrics_file.filename,
                transcripts_filename=transcripts_file.filename)
    
    # Parse force override if provided
    override_dict = None
    if force_role_override:
        try:
            import json
            override_dict = json.loads(force_role_override)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid force_role_override JSON")
    
    # Save uploaded files to temporary locations
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as metrics_temp:
        metrics_content = await metrics_file.read()
        metrics_temp.write(metrics_content)
        metrics_temp_path = metrics_temp.name
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as transcripts_temp:
        transcripts_content = await transcripts_file.read()
        transcripts_temp.write(transcripts_content)
        transcripts_temp_path = transcripts_temp.name
    
    try:
        # Process files
        plan, report = await processor.process_files(
            metrics_temp_path, transcripts_temp_path, db, override_dict
        )
        
        logger.info("Auto ingest completed",
                   total_processed=report['total_processed'],
                   successful=report['successful'],
                   errors_count=len(report['errors']))
        
        return {
            "success": True,
            "data": {
                "plan": plan,
                "report": report
            }
        }
        
    except Exception as e:
        logger.error("Auto ingest failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")
    
    finally:
        # Clean up temporary files
        try:
            os.unlink(metrics_temp_path)
            os.unlink(transcripts_temp_path)
        except:
            pass

@app.post("/api/ingest/from-gcs")
async def ingest_from_gcs(
    force_role_override: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Load and ingest CSV files from Google Cloud Storage

    Args:
        force_role_override: JSON string with role overrides (optional)

    Returns:
        Ingest plan and report
    """
    logger.info("Starting GCS ingest")

    # Parse force override if provided
    override_dict = None
    if force_role_override:
        try:
            import json
            override_dict = json.loads(force_role_override)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid force_role_override JSON")

    # Initialize GCS client
    gcs_client = GCSClient()

    try:
        # Download CSV files from GCS
        metrics_temp_path, transcripts_temp_path = gcs_client.download_csv_files()

        # Process files
        plan, report = await processor.process_files(
            metrics_temp_path, transcripts_temp_path, db, override_dict
        )

        logger.info("GCS ingest completed",
                   total_processed=report['total_processed'],
                   successful=report['successful'],
                   errors_count=len(report['errors']))

        return {
            "success": True,
            "data": {
                "plan": plan,
                "report": report
            }
        }

    except Exception as e:
        logger.error("GCS ingest failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"GCS ingest failed: {str(e)}")

    finally:
        # Clean up temporary files
        try:
            gcs_client.cleanup_temp_files(metrics_temp_path, transcripts_temp_path)
        except:
            pass

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
