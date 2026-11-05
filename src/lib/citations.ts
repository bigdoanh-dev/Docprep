import type { Citation } from "./api";

/** Group references by document without dropping distinct passages or page locations. */
export function groupCitations(citations: Citation[]): [string, Citation[]][] {
  const unique = [
    ...new Map(
      citations.map((citation) => [citation.passage_id, citation]),
    ).values(),
  ];
  const groups = new Map<string, Citation[]>();
  for (const citation of unique)
    groups.set(citation.document, [
      ...(groups.get(citation.document) ?? []),
      citation,
    ]);
  return [...groups.entries()];
}
