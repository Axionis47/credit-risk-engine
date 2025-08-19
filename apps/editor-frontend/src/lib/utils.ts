import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatWordCount(count: number): string {
  return count.toLocaleString()
}

export function getCoherenceColor(score: number): string {
  if (score >= 0.9) return "bg-green-500"
  if (score >= 0.85) return "bg-yellow-500"
  return "bg-red-500"
}

export function getCoherenceLabel(score: number, passed: boolean): string {
  if (passed) return "PASS"
  return "FAIL"
}

export function copyToClipboard(text: string): Promise<void> {
  return navigator.clipboard.writeText(text)
}

export function sanitizeText(text: string): string {
  // Basic XSS protection - escape HTML entities
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;')
}

export function validateInput(text: string): { isValid: boolean; error?: string } {
  if (!text || !text.trim()) {
    return { isValid: false, error: 'Please enter a draft script' }
  }

  if (text.trim().length < 10) {
    return { isValid: false, error: 'Script must be at least 10 characters long' }
  }

  if (text.length > 10000) {
    return { isValid: false, error: 'Script must be less than 10,000 characters' }
  }

  // Check for potentially malicious content
  const suspiciousPatterns = [
    /<script/i,
    /javascript:/i,
    /on\w+\s*=/i,
    /<iframe/i,
    /<object/i,
    /<embed/i
  ]

  for (const pattern of suspiciousPatterns) {
    if (pattern.test(text)) {
      return { isValid: false, error: 'Script contains potentially unsafe content' }
    }
  }

  return { isValid: true }
}
