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
