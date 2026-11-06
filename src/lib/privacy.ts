// Deterministic minimisation, not complete PII recognition.
export function minimiseText(text: string): string {
  return text
    .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, "[REDACTED]")
    .replace(/(?<!\w)(?:\+?84|0)(?:[ .-]?\d){9,10}(?!\w)/g, "[REDACTED]")
    .replace(/\b(?:\d{12}|\d{9})\b/g, "[REDACTED]")
    .replace(/\b(?:at|rt)_[A-Za-z0-9_-]+\b/g, "[REDACTED]")
    .replace(/\bHV-[A-Za-z0-9-]+\b/gi, "[REDACTED]")
    .replace(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g, "[REDACTED]")
    .replace(/\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b/gi, "[REDACTED]")
    .replace(/Bearer\s+\S+/gi, "[REDACTED]");
}
