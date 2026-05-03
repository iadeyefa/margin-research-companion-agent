"""Seed a small demo workspace for local exploration."""

from app.db.session import SessionLocal
from app.models.research_saved_paper import ResearchSavedPaper
from app.models.research_workspace import ResearchWorkspace
from app.models.research_workspace_brief import ResearchWorkspaceBrief


def main() -> None:
    db = SessionLocal()
    try:
        workspace = ResearchWorkspace(title="Demo: Reinforcement learning")
        db.add(workspace)
        db.flush()

        papers = [
            ResearchSavedPaper(
                workspace_id=workspace.id,
                source="openalex",
                external_id="demo-rl-intro",
                title="Reinforcement Learning: An Introduction",
                abstract="A broad introduction to reinforcement learning foundations and algorithms.",
                authors=["Richard S. Sutton", "Andrew G. Barto"],
                venue="MIT Press",
                year=2018,
                publication_date=None,
                doi=None,
                url="http://incompleteideas.net/book/the-book-2nd.html",
                pdf_url=None,
                citation_count=10000,
                open_access=True,
            ),
            ResearchSavedPaper(
                workspace_id=workspace.id,
                source="semantic_scholar",
                external_id="demo-sac",
                title="Soft Actor-Critic: Off-Policy Maximum Entropy Deep Reinforcement Learning",
                abstract="Introduces an off-policy actor-critic algorithm based on maximum entropy RL.",
                authors=["Tuomas Haarnoja", "Aurick Zhou", "Pieter Abbeel", "Sergey Levine"],
                venue="ICML",
                year=2018,
                publication_date=None,
                doi=None,
                url="https://arxiv.org/abs/1801.01290",
                pdf_url="https://arxiv.org/pdf/1801.01290",
                citation_count=5000,
                open_access=True,
            ),
        ]
        db.add_all(papers)
        db.add(
            ResearchWorkspaceBrief(
                workspace_id=workspace.id,
                mode="summary",
                style="balanced",
                title="Demo summary",
                body="Overview\n\nThis demo brief shows persisted synthesis history with source paper snapshots [1], [2].",
                source_papers=[
                    {
                        "source": paper.source,
                        "external_id": paper.external_id,
                        "title": paper.title,
                        "abstract": paper.abstract,
                        "authors": paper.authors,
                        "venue": paper.venue,
                        "year": paper.year,
                        "publication_date": paper.publication_date,
                        "doi": paper.doi,
                        "url": paper.url,
                        "pdf_url": paper.pdf_url,
                        "citation_count": paper.citation_count,
                        "open_access": paper.open_access,
                    }
                    for paper in papers
                ],
            )
        )
        db.commit()
        print(f"Seeded workspace {workspace.id}: {workspace.title}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
