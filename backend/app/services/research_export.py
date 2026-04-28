def _bibtex_key(paper: dict, index: int) -> str:
    first_author = (paper.get("authors") or ["paper"])[0].split()[-1].lower()
    year = paper.get("year") or "nd"
    return f"{first_author}{year}{index}"


def export_bibtex(papers: list[dict]) -> str:
    entries: list[str] = []
    for index, paper in enumerate(papers, start=1):
        authors = " and ".join(paper.get("authors") or [])
        fields = {
            "title": paper.get("title"),
            "author": authors or None,
            "year": str(paper.get("year")) if paper.get("year") else None,
            "journal": paper.get("venue"),
            "doi": paper.get("doi"),
            "url": paper.get("url"),
        }
        lines = [f"@article{{{_bibtex_key(paper, index)},"]
        for key, value in fields.items():
            if value:
                lines.append(f"  {key} = {{{value}}},")
        lines.append("}")
        entries.append("\n".join(lines))
    return "\n\n".join(entries)


def export_markdown(papers: list[dict]) -> str:
    lines = ["# Reading List", ""]
    for paper in papers:
        authors = ", ".join(paper.get("authors") or []) or "Unknown authors"
        venue_bits = [bit for bit in [paper.get("venue"), str(paper.get("year") or "")] if bit]
        venue = " · ".join(venue_bits)
        lines.append(f"- **{paper.get('title', 'Untitled')}**")
        lines.append(f"  - Authors: {authors}")
        if venue:
            lines.append(f"  - Venue: {venue}")
        if paper.get("doi"):
            lines.append(f"  - DOI: {paper['doi']}")
        if paper.get("url"):
            lines.append(f"  - Link: {paper['url']}")
        if paper.get("abstract"):
            lines.append(f"  - Summary: {paper['abstract']}")
        lines.append("")
    return "\n".join(lines).strip()
