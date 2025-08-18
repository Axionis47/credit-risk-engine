import { z } from 'zod';
import { VideoIdSchema, PerformanceMetricsSchema } from './common';

// Retrieve request
export const RetrieveRequestSchema = z.object({
  draft_body: z.string().min(1).max(10000),
});

export type RetrieveRequest = z.infer<typeof RetrieveRequestSchema>;

// Reference script
export const ReferenceScriptSchema = z.object({
  video_id: VideoIdSchema,
  body: z.string(),
  duration_seconds: z.number().min(0).max(180),
  performance: PerformanceMetricsSchema,
  similarity_score: z.number().min(0).max(1),
  performance_score: z.number().min(0).max(1),
  combined_score: z.number().min(0).max(1),
});

export type ReferenceScript = z.infer<typeof ReferenceScriptSchema>;

// Retrieve response
export const RetrieveResponseSchema = z.object({
  ref: ReferenceScriptSchema.nullable(),
  alternates: z.array(ReferenceScriptSchema).max(5),
  total_candidates: z.number().int().min(0),
  search_time_ms: z.number().min(0),
  reason: z.string().optional(), // If ref is null, explains why
});

export type RetrieveResponse = z.infer<typeof RetrieveResponseSchema>;
