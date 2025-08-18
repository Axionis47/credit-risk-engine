import { z } from 'zod';

// Common response wrapper
export const ApiResponseSchema = <T extends z.ZodTypeAny>(dataSchema: T) =>
  z.object({
    success: z.boolean(),
    data: dataSchema.optional(),
    error: z.string().optional(),
    trace_id: z.string().optional(),
  });

export type ApiResponse<T> = {
  success: boolean;
  data?: T;
  error?: string;
  trace_id?: string;
};

// Health check
export const HealthCheckSchema = z.object({
  status: z.literal('healthy'),
  timestamp: z.string(),
  service: z.string(),
  version: z.string(),
});

export type HealthCheck = z.infer<typeof HealthCheckSchema>;

// Error response
export const ErrorResponseSchema = z.object({
  success: z.literal(false),
  error: z.string(),
  details: z.record(z.any()).optional(),
  trace_id: z.string().optional(),
});

export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;

// Video ID validation
export const VideoIdSchema = z.string().regex(/^[A-Za-z0-9_-]{6,50}$/, 'Invalid video ID format');

// Coherence score
export const CoherenceScoreSchema = z.object({
  score: z.number().min(0).max(1),
  notes: z.string().optional(),
  passed: z.boolean(),
});

export type CoherenceScore = z.infer<typeof CoherenceScoreSchema>;

// Performance metrics
export const PerformanceMetricsSchema = z.object({
  views: z.number().int().min(0),
  ctr: z.number().min(0).max(1).optional(),
  avg_view_duration_s: z.number().min(0).optional(),
  retention_30s: z.number().min(0).max(1).optional(),
  published_at: z.string().datetime().optional(),
  asof_date: z.string().datetime().optional(),
});

export type PerformanceMetrics = z.infer<typeof PerformanceMetricsSchema>;
