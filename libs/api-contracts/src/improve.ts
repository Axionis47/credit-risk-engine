import { z } from 'zod';
import { CoherenceScoreSchema } from './common';
import { ReferenceScriptSchema } from './retrieve';

// Improve request
export const ImproveRequestSchema = z.object({
  draft_body: z.string().min(1).max(10000),
  reference: ReferenceScriptSchema.optional(),
  target_word_count: z.number().int().min(100).max(2000).default(900),
  style_notes: z.string().max(500).optional(),
});

export type ImproveRequest = z.infer<typeof ImproveRequestSchema>;

// Improved script
export const ImprovedScriptSchema = z.object({
  title: z.string().min(1).max(200),
  hook: z.string().min(1).max(500),
  body: z.string().min(100).max(5000),
  word_count: z.number().int().min(0),
  coherence: CoherenceScoreSchema,
  diff_summary: z.string().optional(),
  style_principles: z.array(z.string()).optional(),
});

export type ImprovedScript = z.infer<typeof ImprovedScriptSchema>;

// Improve response
export const ImproveResponseSchema = z.object({
  result: ImprovedScriptSchema,
  warnings: z.array(z.string()),
  processing_time_ms: z.number().min(0),
  tuner_passes: z.number().int().min(0).max(1),
});

export type ImproveResponse = z.infer<typeof ImproveResponseSchema>;
