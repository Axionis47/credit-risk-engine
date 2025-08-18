import { z } from 'zod';

// User info
export const UserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  name: z.string(),
  picture: z.string().url().optional(),
  verified_email: z.boolean().optional(),
});

export type User = z.infer<typeof UserSchema>;

// OAuth callback
export const OAuthCallbackSchema = z.object({
  code: z.string(),
  state: z.string().optional(),
});

export type OAuthCallback = z.infer<typeof OAuthCallbackSchema>;

// JWT token response
export const TokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.literal('Bearer'),
  expires_in: z.number(),
  user: UserSchema,
});

export type TokenResponse = z.infer<typeof TokenResponseSchema>;

// Whoami response
export const WhoamiResponseSchema = z.object({
  user: UserSchema,
  authenticated: z.boolean(),
});

export type WhoamiResponse = z.infer<typeof WhoamiResponseSchema>;
