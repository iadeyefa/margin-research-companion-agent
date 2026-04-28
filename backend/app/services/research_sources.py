import asyncio
import xml.etree.ElementTree as ET
from html import unescape
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.core.config import get_settings


settings = get_settings()

SUPPORTED_SOURCES = ("crossref", "semantic_scholar", "openalex", "pubmed", "arxiv")


def _strip_tags(value: str | None) -> str | None:
    if not value:
        return None
    return unescape(
        value.replace("<jats:p>", " ")
        .replace("</jats:p>", " ")
        .replace("<p>", " ")
        .replace("</p>", " ")
        .strip()
    )


def _clean_list(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()]


async def _search_crossref(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, Any]]:
    params = {
        "query.bibliographic": query,
        "rows": limit,
    }
    if settings.research_contact_email:
        params["mailto"] = settings.research_contact_email

    response = await client.get("https://api.crossref.org/works", params=params)
    response.raise_for_status()
    items = response.json().get("message", {}).get("items", [])

    results = []
    for item in items:
        authors = []
        for author in item.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            full_name = " ".join(part for part in [given, family] if part).strip()
            if full_name:
                authors.append(full_name)

        published_parts = (
            item.get("published-print", {}).get("date-parts")
            or item.get("published-online", {}).get("date-parts")
            or []
        )
        year = published_parts[0][0] if published_parts and published_parts[0] else None

        results.append(
            {
                "source": "crossref",
                "external_id": item.get("DOI", ""),
                "title": (item.get("title") or ["Untitled"])[0],
                "abstract": _strip_tags(item.get("abstract")),
                "authors": _clean_list(authors),
                "venue": (item.get("container-title") or [None])[0],
                "year": year,
                "publication_date": None,
                "doi": item.get("DOI"),
                "url": item.get("URL"),
                "pdf_url": None,
                "citation_count": item.get("is-referenced-by-count"),
                "open_access": None,
            }
        )

    return results


async def _search_semantic_scholar(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "limit": limit,
        "fields": "paperId,title,abstract,authors,year,venue,url,openAccessPdf,citationCount,externalIds",
    }
    headers = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key

    response = await client.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params=params,
        headers=headers,
    )
    response.raise_for_status()
    items = response.json().get("data", [])

    return [
        {
            "source": "semantic_scholar",
            "external_id": item.get("paperId", ""),
            "title": item.get("title", "Untitled"),
            "abstract": item.get("abstract"),
            "authors": _clean_list([author.get("name", "") for author in item.get("authors", [])]),
            "venue": item.get("venue"),
            "year": item.get("year"),
            "publication_date": None,
            "doi": item.get("externalIds", {}).get("DOI"),
            "url": item.get("url"),
            "pdf_url": item.get("openAccessPdf", {}).get("url"),
            "citation_count": item.get("citationCount"),
            "open_access": bool(item.get("openAccessPdf", {}).get("url")),
        }
        for item in items
    ]


async def _search_openalex(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, Any]]:
    params = {
        "search": query,
        "per-page": limit,
    }
    if settings.openalex_api_key:
        params["api_key"] = settings.openalex_api_key
    if settings.research_contact_email:
        params["mailto"] = settings.research_contact_email

    response = await client.get("https://api.openalex.org/works", params=params)
    response.raise_for_status()
    items = response.json().get("results", [])

    results = []
    for item in items:
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        open_access = item.get("open_access") or {}
        results.append(
            {
                "source": "openalex",
                "external_id": item.get("id", ""),
                "title": item.get("title", "Untitled"),
                "abstract": None,
                "authors": _clean_list(
                    [
                        authorship.get("author", {}).get("display_name", "")
                        for authorship in item.get("authorships", [])
                    ]
                ),
                "venue": source.get("display_name"),
                "year": item.get("publication_year"),
                "publication_date": item.get("publication_date"),
                "doi": (item.get("doi") or "").replace("https://doi.org/", "") or None,
                "url": item.get("id"),
                "pdf_url": primary_location.get("pdf_url"),
                "citation_count": item.get("cited_by_count"),
                "open_access": open_access.get("is_oa"),
            }
        )

    return results


async def _search_pubmed(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, Any]]:
    search_response = await client.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={"db": "pubmed", "retmode": "json", "retmax": limit, "term": query},
    )
    search_response.raise_for_status()
    ids = search_response.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    summary_response = await client.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        params={"db": "pubmed", "retmode": "json", "id": ",".join(ids)},
    )
    summary_response.raise_for_status()
    payload = summary_response.json().get("result", {})

    results = []
    for pubmed_id in ids:
        item = payload.get(pubmed_id, {})
        authors = _clean_list([author.get("name", "") for author in item.get("authors", [])])
        pubdate = item.get("pubdate")
        year = None
        if pubdate:
            for token in pubdate.split():
                if token.isdigit() and len(token) == 4:
                    year = int(token)
                    break

        results.append(
            {
                "source": "pubmed",
                "external_id": pubmed_id,
                "title": item.get("title", "Untitled"),
                "abstract": None,
                "authors": authors,
                "venue": item.get("fulljournalname"),
                "year": year,
                "publication_date": pubdate,
                "doi": None,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
                "pdf_url": None,
                "citation_count": None,
                "open_access": None,
            }
        )

    return results


async def _search_arxiv(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, Any]]:
    search_query = quote_plus(query)
    response = await client.get(
        f"https://export.arxiv.org/api/query?search_query=all:{search_query}&start=0&max_results={limit}"
    )
    response.raise_for_status()

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(response.text)
    results = []

    for entry in root.findall("atom:entry", namespace):
        paper_id = (entry.findtext("atom:id", default="", namespaces=namespace) or "").strip()
        title = (entry.findtext("atom:title", default="Untitled", namespaces=namespace) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=namespace) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=namespace) or "").strip()
        year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None
        authors = _clean_list(
            [
                (author.findtext("atom:name", default="", namespaces=namespace) or "").strip()
                for author in entry.findall("atom:author", namespace)
            ]
        )
        pdf_url = None
        for link in entry.findall("atom:link", namespace):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href")
                break

        results.append(
            {
                "source": "arxiv",
                "external_id": paper_id.rsplit("/", maxsplit=1)[-1],
                "title": title,
                "abstract": summary,
                "authors": authors,
                "venue": "arXiv",
                "year": year,
                "publication_date": published,
                "doi": None,
                "url": paper_id,
                "pdf_url": pdf_url,
                "citation_count": None,
                "open_access": True,
            }
        )

    return results


def _dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for result in results:
        key = (result.get("doi") or f"{result['source']}::{result['external_id']}").lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


async def search_publications(
    query: str,
    limit_per_source: int = 5,
    sources: list[str] | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    open_access_only: bool = False,
    sort_by: str = "relevance",
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    chosen_sources = [source for source in (sources or list(SUPPORTED_SOURCES)) if source in SUPPORTED_SOURCES]
    source_errors: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        tasks = {
            "crossref": _search_crossref(client, query, limit_per_source),
            "semantic_scholar": _search_semantic_scholar(client, query, limit_per_source),
            "openalex": _search_openalex(client, query, limit_per_source),
            "pubmed": _search_pubmed(client, query, limit_per_source),
            "arxiv": _search_arxiv(client, query, limit_per_source),
        }

        gathered = await asyncio.gather(
            *(tasks[source] for source in chosen_sources),
            return_exceptions=True,
        )

    merged_results: list[dict[str, Any]] = []
    for source, result in zip(chosen_sources, gathered, strict=True):
        if isinstance(result, Exception):
            source_errors[source] = str(result)
            continue
        merged_results.extend(result)

    filtered_results = _dedupe_results(merged_results)

    if year_from is not None:
        filtered_results = [
            item for item in filtered_results if item.get("year") is not None and int(item["year"]) >= year_from
        ]
    if year_to is not None:
        filtered_results = [
            item for item in filtered_results if item.get("year") is not None and int(item["year"]) <= year_to
        ]
    if open_access_only:
        filtered_results = [item for item in filtered_results if item.get("open_access")]

    if sort_by == "newest":
        filtered_results.sort(
            key=lambda item: (
                item.get("year") is None,
                -(item.get("year") or 0),
                item.get("citation_count") is None,
                -(item.get("citation_count") or 0),
            )
        )
    elif sort_by == "most_cited":
        filtered_results.sort(
            key=lambda item: (
                item.get("citation_count") is None,
                -(item.get("citation_count") or 0),
                -(item.get("year") or 0),
            )
        )
    else:
        filtered_results.sort(
            key=lambda item: (
                item.get("citation_count") is None,
                -(item.get("citation_count") or 0),
                -(item.get("year") or 0),
            )
        )

    return filtered_results, source_errors
