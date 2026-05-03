"""Shared formatting of paper metadata for LLM prompts (synthesis, reading path)."""


def effective_abstract(paper: dict) -> str:
    return (paper.get("abstract_override") or paper.get("abstract") or "").strip()


def papers_to_llm_context(papers: list[dict]) -> str:
    lines: list[str] = []
    for index, paper in enumerate(papers, start=1):
        authors = ", ".join(paper.get("authors") or []) or "Unknown authors"
        user_abs = (paper.get("abstract_override") or "").strip()
        catalog_abs = (paper.get("abstract") or "").strip()
        if user_abs:
            abstract_block = f"Abstract (provided by the user — treat as authoritative for this paper):\n{user_abs}"
        elif catalog_abs:
            abstract_block = f"Abstract (from open metadata catalogs):\n{catalog_abs}"
        else:
            abstract_block = (
                "Abstract: not available from connected catalogs.\n"
                "Rely only on title, venue, year, citation count, DOI, and URL below. "
                "Do not invent specific methods, results, or claims as if you had read an abstract. "
                "You may describe what the title suggests only as clearly hedged speculation, "
                "and call out this limitation under Gaps Or Caveats when relevant."
            )
        doi = paper.get("doi") or "—"
        url = paper.get("url") or "—"
        lines.append(
            "\n".join(
                [
                    f"Paper {index}: {paper.get('title', 'Untitled')}",
                    f"Source: {paper.get('source', 'unknown')}",
                    f"Authors: {authors}",
                    f"Venue: {paper.get('venue') or 'Unknown venue'}",
                    f"Year: {paper.get('year') or 'Unknown'}",
                    f"Citations: {paper.get('citation_count') if paper.get('citation_count') is not None else 'Unknown'}",
                    f"DOI: {doi}",
                    f"URL: {url}",
                    abstract_block,
                ]
            )
        )
    return "\n\n".join(lines)
