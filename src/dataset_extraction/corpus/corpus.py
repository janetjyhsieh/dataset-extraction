import re
import logging
import json
from abc import ABC, abstractmethod
from pydantic import BaseModel

from dataset_extraction.corpus.utils import download_pdf


logger = logging.getLogger("dataset_extraction.corpus.corpus")

class SourcePaper(BaseModel):
    paper_id: str
    title: str
    authors: list[str]
    pdf_url: str | None = None
    pdf_path: str | None = None
    venue: str | None = None
    year: int | None = None

class CorpusSource(ABC):
    def __init__(self, working_dir, index_path):
        self.working_dir = working_dir
        self.index_path = index_path
        self.papers: list[SourcePaper] = []
        self.paper_ids: set(str) = set()

        # load existing index.json papers
        if index_path.exists():
            with open(index_path) as f:
                for line in f:
                    if line.strip():
                        rec = json.loads(line)
                        self.papers.append(SourcePaper(**rec))
                        self.paper_ids.add(rec["paper_id"])
            logger.info("Loaded %d existing paper(s) from %s", len(self.papers), index_path)


    @abstractmethod
    def get_papers(self, **kwargs) -> list[SourcePaper]:
        """
        Add new paper to a list maintained by the class, new_papers: list[SourcePaper],
        and return a list of paper_id for each new paper.
        """
        pass

    def download_and_save_papers(self, new_papers: list[SourcePaper]):
        logger.info(f"Downloading and saving {len(new_papers)} new papers...")
        for paper in new_papers:
            safe_id = re.sub(r"[^a-z0-9_-]", "_", paper.paper_id.lower())
            pdf_path = self.working_dir / "pdfs" / f"{safe_id}.pdf"
            try:
                pdf_path = download_pdf(paper.pdf_url, pdf_path)
            except Exception as e:
                logger.warning(f"Failed to download '{paper.title}': {e}")
                continue
            paper.pdf_path = str(pdf_path)
            with open(self.index_path, "a") as f:
                f.write(json.dumps(paper.model_dump()) + "\n")