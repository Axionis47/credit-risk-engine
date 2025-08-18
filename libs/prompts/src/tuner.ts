export interface TunerContext {
  title: string;
  body: string;
  coherenceIssues: string;
  targetScore: number;
}

export const TUNER_PROMPT_V1 = `You are an expert content tuner specializing in fixing coherence issues between video titles and their content. Your task is to make minimal, targeted adjustments to improve title-content alignment.

## Current Title
"{{title}}"

## Current Script
\`\`\`
{{body}}
\`\`\`

## Coherence Issues Identified
{{coherenceIssues}}

## Target Coherence Score
{{targetScore}} (must achieve ≥0.85)

## Your Task

Make the **minimal necessary changes** to either the title OR the content (or both) to achieve coherence ≥0.85. Prioritize:

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

\`\`\`json
{
  "title": "Adjusted title (if changed)",
  "body": "Adjusted script (if changed)", 
  "changes_made": "Brief description of what was changed and why",
  "expected_coherence": 0.90
}
\`\`\`

**Important**: Only include fields that were actually changed. If the title wasn't changed, don't include the "title" field. Same for "body".

Focus on surgical precision - make the smallest changes that solve the coherence problem while preserving the content's strengths.`;

export const TUNER_SYSTEM_PROMPT = `You are an expert content tuner who specializes in making precise adjustments to improve title-content coherence. You understand how to maintain engagement while ensuring accuracy and truthfulness.`;
