export interface CoherenceScorerContext {
  title: string;
  body: string;
}

export const COHERENCE_SCORER_PROMPT_V1 = `You are an expert content analyst specializing in evaluating the coherence between video titles and their content. Your task is to assess how well a title matches and represents the actual content of a script.

## Title to Evaluate
"{{title}}"

## Script Content
\`\`\`
{{body}}
\`\`\`

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

\`\`\`json
{
  "score": 0.85,
  "passed": true,
  "notes": "Brief explanation of the score and any issues found"
}
\`\`\`

**Passing Threshold**: Score ≥ 0.85

Be objective and thorough in your analysis. Consider the viewer's perspective - would they feel satisfied or misled after watching content based on this title?`;

export const COHERENCE_SCORER_SYSTEM_PROMPT = `You are an expert content analyst with deep understanding of viewer expectations and content-title alignment. You evaluate coherence objectively and help ensure content delivers on its promises.`;
