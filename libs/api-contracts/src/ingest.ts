import { z } from 'zod';
import { VideoIdSchema, PerformanceMetricsSchema } from './common';

// CSV role detection
export const CsvRoleSchema = z.enum(['metrics', 'transcripts']);
export type CsvRole = z.infer<typeof CsvRoleSchema>;

// Column mapping
export const ColumnMappingSchema = z.object({
  video_id: z.string(),
  // Metrics columns
  views: z.string().optional(),
  ctr: z.string().optional(),
  avg_view_duration_s: z.string().optional(),
  retention_30s: z.string().optional(),
  published_at: z.string().optional(),
  asof_date: z.string().optional(),
  // Transcripts columns
  transcript: z.string().optional(),
  body: z.string().optional(),
  text: z.string().optional(),
});

export type ColumnMapping = z.infer<typeof ColumnMappingSchema>;

// Ingest plan
export const IngestPlanSchema = z.object({
  metrics_file: z.object({
    role: z.literal('metrics'),
    columns: ColumnMappingSchema,
    row_count: z.number().int().min(0),
    sample_rows: z.array(z.record(z.string())).max(5),
  }),
  transcripts_file: z.object({
    role: z.literal('transcripts'),
    columns: ColumnMappingSchema,
    row_count: z.number().int().min(0),
    sample_rows: z.array(z.record(z.string())).max(5),
  }),
  dataset_last_date: z.string().datetime(),
  embed_cutoff: z.string().datetime(),
  estimated_processing_time_minutes: z.number().min(0),
});

export type IngestPlan = z.infer<typeof IngestPlanSchema>;

// Ingest report
export const IngestReportSchema = z.object({
  total_processed: z.number().int().min(0),
  successful: z.number().int().min(0),
  buckets: z.object({
    metrics_only: z.number().int().min(0),
    transcripts_only: z.number().int().min(0),
    invalid_video_id: z.number().int().min(0),
    too_long: z.number().int().min(0),
    too_fresh: z.number().int().min(0),
    unknown_age: z.number().int().min(0),
  }),
  embeddings_created: z.number().int().min(0),
  processing_time_seconds: z.number().min(0),
  errors: z.array(z.string()),
});

export type IngestReport = z.infer<typeof IngestReportSchema>;

// Auto ingest request (multipart form)
export const AutoIngestRequestSchema = z.object({
  metrics_file: z.any(), // File upload
  transcripts_file: z.any(), // File upload
  force_role_override: z.object({
    metrics_filename: CsvRoleSchema.optional(),
    transcripts_filename: CsvRoleSchema.optional(),
  }).optional(),
});

export type AutoIngestRequest = z.infer<typeof AutoIngestRequestSchema>;

// Auto ingest response
export const AutoIngestResponseSchema = z.object({
  plan: IngestPlanSchema,
  report: IngestReportSchema,
});

export type AutoIngestResponse = z.infer<typeof AutoIngestResponseSchema>;
