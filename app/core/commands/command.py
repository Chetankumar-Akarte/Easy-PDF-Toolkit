from __future__ import annotations

from abc import ABC, abstractmethod


class Command(ABC):
    description: str

    @abstractmethod
    def do(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def undo(self) -> None:
        raise NotImplementedError


class CommandHistory:
    def __init__(self) -> None:
        self._commands: list[Command] = []
        self._position = 0
        self._clean_position = 0

    @property
    def can_undo(self) -> bool:
        return self._position > 0

    @property
    def can_redo(self) -> bool:
        return self._position < len(self._commands)

    @property
    def is_dirty(self) -> bool:
        return self._clean_position < 0 or self._position != self._clean_position

    @property
    def undo_description(self) -> str:
        return self._commands[self._position - 1].description if self.can_undo else ""

    @property
    def redo_description(self) -> str:
        return self._commands[self._position].description if self.can_redo else ""

    def execute(self, command: Command) -> None:
        command.do()
        if self._position < len(self._commands):
            del self._commands[self._position:]
            if self._clean_position > self._position:
                self._clean_position = -1
        self._commands.append(command)
        self._position += 1

    def undo(self) -> Command | None:
        if not self.can_undo:
            return None
        command = self._commands[self._position - 1]
        command.undo()
        self._position -= 1
        return command

    def redo(self) -> Command | None:
        if not self.can_redo:
            return None
        command = self._commands[self._position]
        command.do()
        self._position += 1
        return command

    def mark_clean(self) -> None:
        self._clean_position = self._position

    def clear(self) -> None:
        self._commands.clear()
        self._position = 0
        self._clean_position = 0
