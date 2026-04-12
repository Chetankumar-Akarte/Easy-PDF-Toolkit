from pathlib import Path

from app.infra.storage.recent_files_repo import RecentFilesRepository


def test_recent_files_keeps_unique_and_ordered(tmp_path: Path) -> None:
    repo = RecentFilesRepository(tmp_path, max_items=3)

    repo.add("a.pdf")
    repo.add("b.pdf")
    repo.add("a.pdf")
    repo.add("c.pdf")

    assert repo.load() == ["c.pdf", "a.pdf", "b.pdf"]
