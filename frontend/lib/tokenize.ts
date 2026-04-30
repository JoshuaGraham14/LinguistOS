export interface TokenPart {
  text: string;
  isWord: boolean;
}

// Keep punctuation/spacing as separate parts so we can preserve original text.
export function splitIntoTokenParts(text: string): TokenPart[] {
  const parts: TokenPart[] = [];
  const re = /(\p{L}[\p{L}\p{M}'’-]*)/gu;
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
