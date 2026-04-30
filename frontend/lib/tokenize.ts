export interface TokenPart {
  text: string;
  isWord: boolean;
}

// Keep punctuation/spacing as separate parts so we can preserve original text.
export function splitIntoTokenParts(text: string): TokenPart[] {
  const parts: TokenPart[] = [];
  // Mirrors backend token regex semantics to keep resolve spans aligned with
  // frontend rendering (letters/numbers/underscore plus apostrophes).
  const re = /([\p{L}\p{N}_][\p{L}\p{N}\p{M}_'’-]*)/gu;
  let last = 0;
  for (const match of text.matchAll(re)) {
    const index = match.index ?? 0;
    if (index > last) {
      parts.push({ text: text.slice(last, index), isWord: false });
    }
    const token = match[0];
    parts.push({ text: token, isWord: true });
    last = index + token.length;
  }
  if (last < text.length) {
    parts.push({ text: text.slice(last), isWord: false });
  }
  return parts;
}

export function normalizeToken(token: string): string {
  return token
    .trim()
    .toLowerCase()
    .replace(/[.,!?¿¡;:"“”()\[\]{}]/g, "");
}
