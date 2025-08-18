import json
import time
from typing import Dict, Any, Optional, Tuple
import anthropic
import structlog

from app.config import settings
from app.prompt_renderer import PromptRenderer

logger = structlog.get_logger()

class EditorService:
    """Service for improving scripts using Anthropic Claude"""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.model_name
        self.max_tokens = settings.max_tokens
        self.temperature = settings.temperature
        self.coherence_threshold = settings.coherence_threshold
        self.max_tuner_passes = settings.max_tuner_passes
        
        self.prompt_renderer = PromptRenderer()
    
    async def improve_script(self, draft_body: str, reference_script: Optional[Dict[str, Any]] = None,
                           target_word_count: int = None, style_notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Improve a draft script using Anthropic Claude
        
        Args:
            draft_body: Draft script text
            reference_script: Optional reference script with performance data
            target_word_count: Target word count (default from settings)
            style_notes: Optional style requirements
            
        Returns:
            Improved script with coherence score and metadata
        """
        start_time = time.time()
        
        if target_word_count is None:
            target_word_count = settings.target_word_count
        
        try:
            # Generate improved script
            improved_script = await self._generate_improved_script(
                draft_body, reference_script, target_word_count, style_notes
            )
            
            # Check coherence
            coherence_result = await self._check_coherence(
                improved_script["title"], improved_script["body"]
            )
            
            tuner_passes = 0
            
            # Apply tuner if coherence fails
            if not coherence_result["passed"] and self.max_tuner_passes > 0:
                logger.info("Coherence failed, applying tuner", 
                           score=coherence_result["score"],
                           threshold=self.coherence_threshold)
                
                tuned_result = await self._apply_tuner(
                    improved_script["title"],
                    improved_script["body"],
                    coherence_result["notes"]
                )
                
                if tuned_result:
                    # Update script with tuned version
                    if "title" in tuned_result:
                        improved_script["title"] = tuned_result["title"]
                    if "body" in tuned_result:
                        improved_script["body"] = tuned_result["body"]
                    
                    # Re-check coherence
                    coherence_result = await self._check_coherence(
                        improved_script["title"], improved_script["body"]
                    )
                    
                    tuner_passes = 1
            
            # Calculate warnings
            warnings = []
            word_count = len(improved_script["body"].split())
            
            if word_count < target_word_count * 0.8:
                warnings.append(f"Script is shorter than target ({word_count} vs {target_word_count} words)")
            elif word_count > target_word_count * 1.2:
                warnings.append(f"Script is longer than target ({word_count} vs {target_word_count} words)")
            
            processing_time_ms = (time.time() - start_time) * 1000
            
            logger.info("Script improved", 
                       word_count=word_count,
                       coherence_score=coherence_result["score"],
                       coherence_passed=coherence_result["passed"],
                       tuner_passes=tuner_passes,
                       processing_time_ms=processing_time_ms)
            
            return {
                "result": {
                    "title": improved_script["title"],
                    "hook": improved_script["hook"],
                    "body": improved_script["body"],
                    "word_count": word_count,
                    "coherence": coherence_result,
                    "diff_summary": improved_script.get("diff_summary"),
                    "style_principles": improved_script.get("style_principles", [])
                },
                "warnings": warnings,
                "processing_time_ms": processing_time_ms,
                "tuner_passes": tuner_passes
            }
            
        except Exception as e:
            logger.error("Script improvement failed", error=str(e))
            raise
    
    async def _generate_improved_script(self, draft_body: str, reference_script: Optional[Dict[str, Any]],
                                      target_word_count: int, style_notes: Optional[str]) -> Dict[str, Any]:
        """Generate improved script using Claude"""
        
        # Render prompt
        prompt = self.prompt_renderer.render_script_improver(
            draft_body=draft_body,
            reference_script=reference_script,
            target_word_count=target_word_count,
            style_notes=style_notes
        )
        
        # Call Claude
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system="You are a world-class video script writer with deep expertise in creating viral, engaging content. You understand what makes viewers click, watch, and share. You analyze successful patterns and apply them creatively without copying content.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse JSON response
        content = response.content[0].text
        
        # Extract JSON from response
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in Claude response")
        
        json_str = content[json_start:json_end]
        
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude JSON response", content=content, error=str(e))
            raise ValueError(f"Invalid JSON in Claude response: {str(e)}")
        
        # Validate required fields
        required_fields = ["title", "hook", "body"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field '{field}' in Claude response")
        
        return result
    
    async def _check_coherence(self, title: str, body: str) -> Dict[str, Any]:
        """Check title-body coherence using Claude"""
        
        prompt = self.prompt_renderer.render_coherence_scorer(
            title=title,
            body=body,
            coherence_threshold=self.coherence_threshold
        )
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0.1,  # Lower temperature for scoring
            system="You are an expert content analyst with deep understanding of viewer expectations and content-title alignment. You evaluate coherence objectively and help ensure content delivers on its promises.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        content = response.content[0].text
        
        # Extract JSON from response
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in coherence scorer response")
        
        json_str = content[json_start:json_end]
        
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse coherence scorer JSON", content=content, error=str(e))
            raise ValueError(f"Invalid JSON in coherence scorer response: {str(e)}")
        
        # Validate and normalize
        if "score" not in result:
            raise ValueError("Missing 'score' in coherence response")
        
        score = float(result["score"])
        passed = score >= self.coherence_threshold
        
        return {
            "score": score,
            "passed": passed,
            "notes": result.get("notes", "")
        }
    
    async def _apply_tuner(self, title: str, body: str, coherence_issues: str) -> Optional[Dict[str, Any]]:
        """Apply tuner to fix coherence issues"""
        
        prompt = self.prompt_renderer.render_tuner(
            title=title,
            body=body,
            coherence_issues=coherence_issues,
            target_score=self.coherence_threshold,
            coherence_threshold=self.coherence_threshold
        )
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.3,  # Lower temperature for tuning
                system="You are an expert content tuner who specializes in making precise adjustments to improve title-content coherence. You understand how to maintain engagement while ensuring accuracy and truthfulness.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.warning("No JSON found in tuner response")
                return None
            
            json_str = content[json_start:json_end]
            
            try:
                result = json.loads(json_str)
                return result
            except json.JSONDecodeError as e:
                logger.error("Failed to parse tuner JSON", content=content, error=str(e))
                return None
                
        except Exception as e:
            logger.error("Tuner failed", error=str(e))
            return None
