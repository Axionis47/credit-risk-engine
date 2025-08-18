import { z } from 'zod';

// Idea from Reddit
export const IdeaSchema = z.object({
  idea_id: z.string(),
  title: z.string().min(1).max(300),
  snippet: z.string().min(1).max(1000),
  source_url: z.string().url(),
  subreddit: z.string().min(1).max(50),
  score: z.number().int(),
  num_comments: z.number().int().min(0),
  created_at: z.string().datetime(),
  fetched_at: z.string().datetime(),
});

export type Idea = z.infer<typeof IdeaSchema>;

// User feedback on idea
export const FeedbackTypeSchema = z.enum(['reject', 'save', 'superlike']);
export type FeedbackType = z.infer<typeof FeedbackTypeSchema>;

export const IdeaFeedbackSchema = z.object({
  idea_id: z.string(),
  feedback_type: FeedbackTypeSchema,
  notes: z.string().max(500).optional(),
});

export type IdeaFeedback = z.infer<typeof IdeaFeedbackSchema>;

// Deck response (Tinder-style cards)
export const DeckResponseSchema = z.object({
  ideas: z.array(IdeaSchema).max(20),
  has_more: z.boolean(),
  total_available: z.number().int().min(0),
});

export type DeckResponse = z.infer<typeof DeckResponseSchema>;

// Accepted ideas response
export const AcceptedIdeasResponseSchema = z.object({
  saved: z.array(IdeaSchema.extend({
    saved_at: z.string().datetime(),
    notes: z.string().optional(),
  })),
  superliked: z.array(IdeaSchema.extend({
    superliked_at: z.string().datetime(),
    notes: z.string().optional(),
  })),
  total_count: z.number().int().min(0),
});

export type AcceptedIdeasResponse = z.infer<typeof AcceptedIdeasResponseSchema>;

// Reddit sync request
export const RedditSyncRequestSchema = z.object({
  subreddits: z.array(z.string()).min(1).max(20).optional(),
  max_posts_per_subreddit: z.number().int().min(1).max(100).default(50),
  min_score: z.number().int().min(0).default(10),
  max_age_hours: z.number().int().min(1).max(168).default(24), // 1 week max
});

export type RedditSyncRequest = z.infer<typeof RedditSyncRequestSchema>;

// Reddit sync response
export const RedditSyncResponseSchema = z.object({
  inserted: z.number().int().min(0),
  skipped_duplicates: z.number().int().min(0),
  errors: z.array(z.string()),
  processing_time_seconds: z.number().min(0),
  subreddits_processed: z.array(z.string()),
});

export type RedditSyncResponse = z.infer<typeof RedditSyncResponseSchema>;
