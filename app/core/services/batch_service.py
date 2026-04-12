class BatchService:
    """Coordinates batch PDF tasks with progress and result summaries."""

    def run_batch(self, operation_name: str, inputs: list[str]) -> None:
        _ = (operation_name, inputs)
