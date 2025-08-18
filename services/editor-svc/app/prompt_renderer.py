from jinja2 import Template
from typing import Dict, Any, Optional

class PromptRenderer:
    """Renders prompts using Jinja2 templates"""
    
    def __init__(self):
        # Script improver prompt template
        self.script_improver_template = Template("""You are an expert video script writer specializing in creating engaging, high-performing content. Your task is to improve a draft script by learning from a high-performing reference script.

## Your Mission
Transform the draft into a compelling script that:
1. Captures attention immediately with a strong hook
2. Maintains viewer engagement throughout
3. Delivers clear value and emotional resonance
4. Follows proven structural patterns from successful content

## Reference Script Analysis
{% if reference_script %}
**High-Performing Reference** ({{ reference_script.performance.views }} views{% if reference_script.performance.ctr %}, {{ "%.1f"|format(reference_script.performance.ctr * 100) }}% CTR{% endif %}{% if reference_script.performance.retention_30s %}, {{ "%.1f"|format(reference_script.performance.retention_30s * 100) }}% 30s retention{% endif %}):

```
{{ reference_script.body }}
```

**Key Success Patterns to Learn From:**
- Hook structure and emotional triggers
- Pacing and tension building
- Storytelling techniques
- Language patterns and word choice
- Structural flow and transitions

**CRITICAL: Do NOT copy content. Learn the STYLE and STRUCTURE principles only.**
{% else %}
No reference script provided. Apply general best practices for engaging video content.
{% endif %}

## Draft to Improve
```
{{ draft_body }}
```

{% if style_notes %}
## Additional Style Requirements
{{ style_notes }}
{% endif %}

## Output Requirements

Provide your response in this exact JSON format:

```json
{
  "title": "Compelling title that creates curiosity and urgency",
  "hook": "Opening 15-30 seconds that immediately grabs attention and creates a hook",
  "body": "Complete improved script with natural flow and engagement",
  "word_count": 0,
  "style_principles": ["principle1", "principle2", "principle3"],
  "diff_summary": "Brief summary of key improvements made"
}
```

## Guidelines
- **Target Length**: ~{{ target_word_count }} words (flexible, prioritize engagement over exact count)
- **Hook**: Must create immediate intrigue, curiosity, or emotional connection
- **Structure**: Clear beginning, compelling middle, satisfying conclusion
- **Language**: Conversational, authentic, appropriate for the content type
- **Engagement**: Use techniques like questions, cliffhangers, relatable scenarios
- **Value**: Ensure clear takeaways or emotional payoff for viewers

Focus on creating content that viewers will want to watch to completion and share with others.""")

        # Coherence scorer prompt template
        self.coherence_scorer_template = Template("""You are an expert content analyst specializing in evaluating the coherence between video titles and their content. Your task is to assess how well a title matches and represents the actual content of a script.

## Title to Evaluate
"{{ title }}"

## Script Content
```
{{ body }}
```

## Evaluation Criteria

**Coherence Score (0.0 - 1.0):**
- **1.0**: Perfect alignment - title accurately represents content, sets correct expectations
- **0.9-0.99**: Excellent - minor discrepancies but overall very coherent
- **0.8-0.89**: Good - mostly coherent with some misalignment
- **0.7-0.79**: Fair - noticeable gaps between title and content
- **0.6-0.69**: Poor - significant misalignment
- **0.0-0.59**: Very poor - title misleading or completely unrelated

**Key Factors:**
1. **Accuracy**: Does the title reflect what actually happens in the script?
2. **Expectations**: Would viewers get what they expect from the title?
3. **Completeness**: Does the title capture the main theme/story?
4. **Misleading Elements**: Any clickbait that doesn't deliver?
5. **Tone Match**: Does the title's tone match the content's tone?

## Output Requirements

Provide your response in this exact JSON format:

```json
{
  "score": 0.85,
  "passed": true,
  "notes": "Brief explanation of the score and any issues found"
}
```

**Passing Threshold**: Score ≥ {{ coherence_threshold }}

Be objective and thorough in your analysis. Consider the viewer's perspective - would they feel satisfied or misled after watching content based on this title?""")

        # Tuner prompt template
        self.tuner_template = Template("""You are an expert content tuner specializing in fixing coherence issues between video titles and their content. Your task is to make minimal, targeted adjustments to improve title-content alignment.

## Current Title
"{{ title }}"

## Current Script
```
{{ body }}
```

## Coherence Issues Identified
{{ coherence_issues }}

## Target Coherence Score
{{ target_score }} (must achieve ≥{{ coherence_threshold }})

## Your Task

Make the **minimal necessary changes** to either the title OR the content (or both) to achieve coherence ≥{{ coherence_threshold }}. Prioritize:

1. **Title adjustments** (preferred) - often more efficient
2. **Content adjustments** - only if title changes aren't sufficient
3. **Combination** - if needed for complex misalignments

## Guidelines

**For Title Changes:**
- Maintain the core appeal and click-worthiness
- Ensure accuracy to the actual content
- Keep the emotional hook but make it truthful
- Preserve the target audience and tone

**For Content Changes:**
- Minimal edits to support the title's promise
- Add missing elements the title implies
- Adjust tone/framing to match title expectations
- Maintain the core story and value

## Output Requirements

Provide your response in this exact JSON format:

```json
{
  "title": "Adjusted title (if changed)",
  "body": "Adjusted script (if changed)", 
  "changes_made": "Brief description of what was changed and why",
  "expected_coherence": 0.90
}
```

**Important**: Only include fields that were actually changed. If the title wasn't changed, don't include the "title" field. Same for "body".

Focus on surgical precision - make the smallest changes that solve the coherence problem while preserving the content's strengths.""")
    
    def render_script_improver(self, draft_body: str, reference_script: Optional[Dict[str, Any]] = None,
                             target_word_count: int = 900, style_notes: Optional[str] = None) -> str:
        """Render script improver prompt"""
        return self.script_improver_template.render(
            draft_body=draft_body,
            reference_script=reference_script,
            target_word_count=target_word_count,
            style_notes=style_notes
        )
    
    def render_coherence_scorer(self, title: str, body: str, coherence_threshold: float = 0.85) -> str:
        """Render coherence scorer prompt"""
        return self.coherence_scorer_template.render(
            title=title,
            body=body,
            coherence_threshold=coherence_threshold
        )
    
    def render_tuner(self, title: str, body: str, coherence_issues: str,
                    target_score: float = 0.85, coherence_threshold: float = 0.85) -> str:
        """Render tuner prompt"""
        return self.tuner_template.render(
            title=title,
            body=body,
            coherence_issues=coherence_issues,
            target_score=target_score,
            coherence_threshold=coherence_threshold
        )
