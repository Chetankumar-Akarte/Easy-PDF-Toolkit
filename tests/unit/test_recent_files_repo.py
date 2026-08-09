from pathlib import Path

from app.infra.storage.recent_files_repo import RecentFilesRepository


def test_recent_files_keeps_unique_and_ordered(tmp_path: Path) -> None:
    repo = RecentFilesRepository(tmp_path, max_items=3)
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    third = tmp_path / "c.pdf"

    repo.add(str(first))
    repo.add(str(second))
    repo.add(str(first))
    repo.add(str(third))

    assert repo.load() == [str(third.resolve()), str(first.resolve()), str(second.resolve())]
