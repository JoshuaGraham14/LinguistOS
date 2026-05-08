/**
 * Answer matching for sentence practice (typing + voice modes).
 *
 * The previous logic was a single `normalize(a) === normalize(b)` check, which
 * marked perfectly reasonable answers wrong over trivial differences:
 *   - "futbol"            vs  "fútbol"           (missing diacritic)
 *   - "juego al fútbol"   vs  "yo juego al fútbol" (omitted subject pronoun)
 *
 * In Spanish (and to a lesser extent English) the subject pronoun is often
 * dropped without changing meaning, and diacritics are routinely lost when
 * speaking or typing on a non-Spanish keyboard. We don't want learners to
 * lose flow over those — but we DO still want to catch real mistakes (wrong
 * verb form, wrong word, wrong tense).
 *
 * `checkAnswer` runs three cascading tiers:
 *   1. Exact normalized match.
 *   2. Optional leading subject-pronoun stripped from both sides, then exact.
 *   3. Diacritic-insensitive comparison (stacks on top of 2).
 *
 * Anything that requires steps 2 or 3 is reported as `lenient` so the UI
 * can still show the canonical answer ("yo juego al fútbol") to teach the
 * fuller, more correct form. Callers treat lenient and exact identically
 * for scoring + audio playback — both count as "correct".
 */

export type MatchKind =
  | "exact"
  | "lenient-pronoun"
  | "lenient-diacritic"
  | "lenient-both"
  | "mismatch";

export interface MatchResult {
  /** True for exact and any lenient match. False only for `mismatch`. */
  ok: boolean;
  /** True only when the user's normalized answer matched the expected one byte-for-byte. */
  exact: boolean;
  kind: MatchKind;
}

// ---------------------------------------------------------------------------
// Normalization
// ---------------------------------------------------------------------------

/** Lowercase, collapse whitespace, drop terminal punctuation/quotes. */
function normalize(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/[.,!?¿¡;:"'“”„«»…—–-]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Strip diacritics so e.g. "fútbol" → "futbol", "café" → "cafe". */
function stripDiacritics(s: string): string {
  // Decompose accented chars into base + combining mark, then drop the marks.
  return s.normalize("NFD").replace(/\p{Diacritic}/gu, "");
}

// ---------------------------------------------------------------------------
// Pronoun handling
// ---------------------------------------------------------------------------
//
// We strip a single leading subject pronoun from each side independently. This
// lets "juego al fútbol" match "yo juego al fútbol" without making the matcher
// loose enough to start ignoring real content words.
//
// Lists are intentionally short and conservative: only true subject pronouns,
// nothing reflexive ("me", "te"), nothing object ("lo", "la"), nothing
// possessive ("mi", "tu") — those genuinely change the sentence's meaning.

const SUBJECT_PRONOUNS_ES: ReadonlySet<string> = new Set([
  "yo",
  "tú",
  "tu", // diacritic-stripped form, in case learner typed plain "tu" as subject
  "él",
  "el", // ditto
  "ella",
  "usted",
  "nosotros",
  "nosotras",
  "vosotros",
  "vosotras",
  "ellos",
  "ellas",
  "ustedes",
]);

const SUBJECT_PRONOUNS_EN: ReadonlySet<string> = new Set([
  "i",
  "you",
  "he",
  "she",
  "it",
  "we",
  "they",
]);

/** Combined set used for stripping; we don't know which language the answer is in. */
const ALL_SUBJECT_PRONOUNS: ReadonlySet<string> = new Set([
  ...SUBJECT_PRONOUNS_ES,
  ...SUBJECT_PRONOUNS_EN,
]);

/**
 * If `s` starts with a subject pronoun, drop it (along with the following space).
 * Returns the (possibly unchanged) string. Idempotent — only the first token
 * is considered, so "yo yo juego" → "yo juego" (still leaves the second one).
 */
function stripLeadingPronoun(s: string): string {
  const space = s.indexOf(" ");
  if (space < 0) return s; // single-word answer; leave alone
  const head = s.slice(0, space);
  if (ALL_SUBJECT_PRONOUNS.has(head)) {
    return s.slice(space + 1);
  }
  return s;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Compare a user's answer against the expected sentence using a 3-tier check.
 *
 * @param user      raw text the learner produced (typed or transcribed)
 * @param expected  canonical answer from the sentence generator
 */
export function checkAnswer(user: string, expected: string): MatchResult {
  const u = normalize(user);
  const e = normalize(expected);

  if (!u) return { ok: false, exact: false, kind: "mismatch" };

  // Tier 1: exact normalized match.
  if (u === e) {
    return { ok: true, exact: true, kind: "exact" };
  }

  // Tier 2: pronoun-stripped match (still diacritic-sensitive).
  const uStripped = stripLeadingPronoun(u);
  const eStripped = stripLeadingPronoun(e);
  const pronounDropped = uStripped !== u || eStripped !== e;
  if (pronounDropped && uStripped === eStripped) {
    return { ok: true, exact: false, kind: "lenient-pronoun" };
  }

  // Tier 3: diacritic-insensitive match. Try with and without pronoun
  // stripping so we catch both "futbol"≈"fútbol" and "yo juego al futbol"≈
  // "juego al fútbol" combined cases.
  const uNoDia = stripDiacritics(u);
  const eNoDia = stripDiacritics(e);
  if (uNoDia === eNoDia) {
    return { ok: true, exact: false, kind: "lenient-diacritic" };
  }
  const uStrippedNoDia = stripDiacritics(uStripped);
  const eStrippedNoDia = stripDiacritics(eStripped);
  if (
    pronounDropped &&
    uStrippedNoDia === eStrippedNoDia
  ) {
    return { ok: true, exact: false, kind: "lenient-both" };
  }

  return { ok: false, exact: false, kind: "mismatch" };
}
