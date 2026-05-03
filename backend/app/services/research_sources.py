import asyncio
import re
import xml.etree.ElementTree as ET
from html import unescape
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, quote_plus

import httpx

from app.core.config import get_settings
from app.services.paper_prompt import effective_abstract


settings = get_settings()

SUPPORTED_SOURCES = ("crossref", "semantic_scholar", "openalex", "pubmed", "arxiv")


def _strip_tags(value: Optional[str]) -> Optional[str]:
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


def _xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _openalex_inverted_index_to_abstract(inverted: Optional[Dict[str, Any]]) -> Optional[str]:
    """Rebuild plaintext abstract from OpenAlex ``abstract_inverted_index``."""
    if not inverted or not isinstance(inverted, dict):
        return None
    pairs: list[tuple[int, str]] = []
    for word, positions in inverted.items():
        if not word or not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int):
                pairs.append((pos, str(word)))
    if not pairs:
        return None
    pairs.sort(key=lambda item: item[0])
    return " ".join(w for _, w in pairs)


def _parse_pubmed_efetch_abstracts(xml_text: str) -> dict[str, str]:
    """Map PubMed ID → abstract text from efetch XML."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {}

    mapping: dict[str, str] = {}
    for article in root:
        if _xml_local_name(article.tag) != "PubmedArticle":
            continue
        pmid: Optional[str] = None
        for el in article.iter():
            if _xml_local_name(el.tag) == "PMID" and el.text:
                pmid = el.text.strip()
                break
        if not pmid:
            continue
        abstract_el = None
        for el in article.iter():
            if _xml_local_name(el.tag) == "Abstract":
                abstract_el = el
                break
        if abstract_el is None:
            continue
        parts: list[str] = []
        for child in abstract_el:
            if _xml_local_name(child.tag) != "AbstractText":
                continue
            label = child.attrib.get("Label")
            body = "".join(child.itertext()).strip()
            if not body:
                continue
            if label:
                parts.append(f"{label}: {body}")
            else:
                parts.append(body)
        if parts:
            mapping[pmid] = " ".join(parts)
    return mapping


async def _pubmed_efetch_abstracts_by_ids(
    client: httpx.AsyncClient, pubmed_ids: list[str]
) -> dict[str, str]:
    if not pubmed_ids:
        return {}
    fetch_response = await client.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
        params={"db": "pubmed", "retmode": "xml", "id": ",".join(pubmed_ids)},
    )
    fetch_response.raise_for_status()
    return _parse_pubmed_efetch_abstracts(fetch_response.text)


def _openalex_work_api_url(work_ref: str) -> str:
    w = work_ref.strip()
    if not w:
        return ""
    if w.startswith("https://api.openalex.org/"):
        return w
    if w.startswith("https://openalex.org/"):
        return w.replace("https://openalex.org/", "https://api.openalex.org/", 1)
    return f"https://api.openalex.org/works/{w}"


async def _fetch_semantic_scholar_abstract(client: httpx.AsyncClient, paper_id: str) -> Optional[str]:
    headers: dict[str, str] = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
    response = await client.get(
        f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}",
        params={"fields": "abstract"},
        headers=headers,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json().get("abstract")


async def _fetch_openalex_work_abstract(client: httpx.AsyncClient, work_ref: str) -> Optional[str]:
    url = _openalex_work_api_url(work_ref)
    if not url:
        return None
    params: dict[str, str] = {}
    if settings.openalex_api_key:
        params["api_key"] = settings.openalex_api_key
    if settings.research_contact_email:
        params["mailto"] = settings.research_contact_email
    response = await client.get(url, params=params or None)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return _openalex_inverted_index_to_abstract(data.get("abstract_inverted_index"))


async def _fetch_crossref_work_abstract_by_doi(client: httpx.AsyncClient, doi: str) -> Optional[str]:
    raw = doi.strip().replace("https://doi.org/", "").strip()
    if not raw:
        return None
    params: dict[str, str] = {}
    if settings.research_contact_email:
        params["mailto"] = settings.research_contact_email
    response = await client.get(
        f"https://api.crossref.org/works/{quote(raw, safe=':/')}",
        params=params or None,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    item = response.json().get("message", {})
    return _strip_tags(item.get("abstract"))


async def _fetch_arxiv_record_abstract(client: httpx.AsyncClient, arxiv_id: str) -> Optional[str]:
    aid = arxiv_id.strip()
    if not aid:
        return None
    response = await client.get(
        f"https://export.arxiv.org/api/query?id_list={quote_plus(aid)}&max_results=1",
    )
    response.raise_for_status()
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(response.text)
    for entry in root.findall("atom:entry", namespace):
        summary = (entry.findtext("atom:summary", default="", namespaces=namespace) or "").strip()
        return summary or None
    return None


def _html_to_plain(html: Optional[str]) -> Optional[str]:
    if not html:
        return None
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = " ".join(text.split())
    return text if text else None


async def _fetch_europepmc_abstract(
    client: httpx.AsyncClient,
    *,
    doi: Optional[str] = None,
    pubmed_id: Optional[str] = None,
) -> Optional[str]:
    queries: list[str] = []
    if pubmed_id:
        queries.append(f"EXT_ID:{pubmed_id} AND SRC:MED")
    if doi:
        d = doi.replace("https://doi.org/", "").strip()
        queries.append(f'DOI:"{d}"')
        queries.append(f"DOI:{d}")
    for q in queries:
        try:
            response = await client.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                params={"query": q, "format": "json", "resultType": "core", "pageSize": 1},
                timeout=30,
            )
            response.raise_for_status()
            results = (response.json().get("resultList") or {}).get("result") or []
            if results:
                raw = results[0].get("abstractText") or results[0].get("abstract")
                plain = _html_to_plain(raw) if raw else None
                if plain:
                    return plain
        except Exception:
            continue
    return None


async def _fetch_core_abstract_by_doi(client: httpx.AsyncClient, doi: str) -> Optional[str]:
    key = (settings.core_api_key or "").strip()
    if not key:
        return None
    d = doi.replace("https://doi.org/", "").strip()
    if not d:
        return None
    try:
        response = await client.get(
            "https://api.core.ac.uk/v3/search/works",
            params={"q": f"doi:{d}", "limit": 10},
            headers={"Authorization": f"Bearer {key}"},
            timeout=30,
        )
        if response.status_code in (401, 403):
            return None
        response.raise_for_status()
        data = response.json()
        items: list[Any]
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data") or data.get("results") or []
        else:
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            ab = item.get("abstract")
            if ab and str(ab).strip():
                return str(ab).strip()
    except Exception:
        return None
    return None


async def enrich_missing_abstracts(client: httpx.AsyncClient, papers: list[dict[str, Any]]) -> None:
    """Best-effort: fill empty catalog abstracts on in-memory paper dicts (e.g. before LLM synthesis)."""
    need = [p for p in papers if not effective_abstract(p)]
    if not need:
        return

    pubmed_ids = [str(p["external_id"]) for p in need if p.get("source") == "pubmed" and p.get("external_id")]
    if pubmed_ids:
        pm_map = await _pubmed_efetch_abstracts_by_ids(client, pubmed_ids)
        for p in need:
            if p.get("source") == "pubmed":
                text = pm_map.get(str(p["external_id"]), "")
                if text:
                    p["abstract"] = text

    async def fill(paper: dict[str, Any]) -> None:
        if effective_abstract(paper):
            return
        src = (paper.get("source") or "").strip()
        ext = (paper.get("external_id") or "").strip()
        try:
            abstract: Optional[str] = None
            if src == "semantic_scholar" and ext:
                abstract = await _fetch_semantic_scholar_abstract(client, ext)
            elif src == "openalex" and ext:
                abstract = await _fetch_openalex_work_abstract(client, ext)
            elif src == "crossref" and ext:
                abstract = await _fetch_crossref_work_abstract_by_doi(client, ext)
            elif src == "arxiv" and ext:
                abstract = await _fetch_arxiv_record_abstract(client, ext)
            if abstract:
                paper["abstract"] = abstract
                return
            doi = (paper.get("doi") or "").strip().replace("https://doi.org/", "")
            if doi and src != "crossref":
                fallback = await _fetch_crossref_work_abstract_by_doi(client, doi)
                if fallback:
                    paper["abstract"] = fallback
            if effective_abstract(paper):
                return
            pmid = str(paper.get("external_id") or "").strip() if paper.get("source") == "pubmed" else None
            doi_norm = (paper.get("doi") or "").strip().replace("https://doi.org/", "") or None
            epm = await _fetch_europepmc_abstract(client, doi=doi_norm, pubmed_id=pmid)
            if epm:
                paper["abstract"] = epm
                return
            if doi_norm:
                core_ab = await _fetch_core_abstract_by_doi(client, doi_norm)
                if core_ab:
                    paper["abstract"] = core_ab
        except Exception:
            return

    remaining = [p for p in need if not effective_abstract(p)]
    await asyncio.gather(*[fill(p) for p in remaining])


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
                "abstract": _openalex_inverted_index_to_abstract(item.get("abstract_inverted_index")),
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

    if results:
        abstracts = await _pubmed_efetch_abstracts_by_ids(client, ids)
        for row in results:
            text = abstracts.get(row["external_id"])
            if text:
                row["abstract"] = text

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
        doi = (result.get("doi") or "").strip().lower().replace("https://doi.org/", "")
        title = re.sub(r"[^a-z0-9]+", " ", (result.get("title") or "").lower()).strip()
        year = str(result.get("year") or "")
        keys = {
            f"doi::{doi}" if doi else "",
            f"title::{title}::{year}" if title and year else "",
            f"{result['source']}::{result['external_id']}".lower(),
        }
        keys.discard("")
        if seen.intersection(keys):
            continue
        seen.update(keys)
        deduped.append(result)
    return deduped


async def search_publications(
    query: str,
    limit_per_source: int = 5,
    sources: Optional[List[str]] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    open_access_only: bool = False,
    sort_by: str = "relevance",
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    chosen_sources = [source for source in (sources or list(SUPPORTED_SOURCES)) if source in SUPPORTED_SOURCES]
    source_errors: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        runners = {
            "crossref": lambda: _search_crossref(client, query, limit_per_source),
            "semantic_scholar": lambda: _search_semantic_scholar(client, query, limit_per_source),
            "openalex": lambda: _search_openalex(client, query, limit_per_source),
            "pubmed": lambda: _search_pubmed(client, query, limit_per_source),
            "arxiv": lambda: _search_arxiv(client, query, limit_per_source),
        }

        gathered = await asyncio.gather(
            *(runners[source]() for source in chosen_sources),
            return_exceptions=True,
        )

    merged_results: list[dict[str, Any]] = []
    for source, result in zip(chosen_sources, gathered):
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
