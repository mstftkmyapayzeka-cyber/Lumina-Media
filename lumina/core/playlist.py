"""Çalma listesi mantığı (PlayModes, Karışık/Sıralı, Sıralama, Geçmiş ve Çalma Sırası)."""
from __future__ import annotations

import enum
import os
import random
from typing import List, Optional
from PySide6.QtCore import QObject, Signal

from lumina.core.media_item import MediaItem
from lumina.core.natural_sort import natural_sort_key

class PlayMode(enum.Enum):
    SEQUENTIAL = "sequential"
    SHUFFLE = "shuffle"
    REPEAT_ALL = "repeat_all"
    REPEAT_ONE = "repeat_one"
    STOP_AFTER = "stop_after"

class Playlist(QObject):
    itemsChanged = Signal()
    currentIndexChanged = Signal(int)
    itemUpdated = Signal(int, object)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._items: List[MediaItem] = []
        self._current_index: int = -1
        self._mode = PlayMode.SEQUENTIAL
        self._shuffle_order: List[int] = []
        self._shuffle_pos: int = -1

    # ---------------------------------------------------------------- Temel Erişim
    def items(self) -> List[MediaItem]:
        return list(self._items)

    def count(self) -> int:
        return len(self._items)

    def current_index(self) -> int:
        return self._current_index

    def current_item(self) -> Optional[MediaItem]:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return None

    def set_current_index(self, index: int) -> None:
        if 0 <= index < len(self._items):
            self._current_index = index
            self.currentIndexChanged.emit(index)
        elif not self._items:
            self._current_index = -1
            self.currentIndexChanged.emit(-1)

    # ---------------------------------------------------------------- Çalma Modları
    def mode(self) -> PlayMode:
        return self._mode

    def set_mode(self, mode: PlayMode) -> None:
        self._mode = mode
        if mode == PlayMode.SHUFFLE:
            self._rebuild_shuffle_order()

    def _rebuild_shuffle_order(self) -> None:
        self._shuffle_order = list(range(len(self._items)))
        random.shuffle(self._shuffle_order)
        if self._current_index in self._shuffle_order:
            self._shuffle_order.remove(self._current_index)
            self._shuffle_order.insert(0, self._current_index)
            self._shuffle_pos = 0
        else:
            self._shuffle_pos = -1

    # ---------------------------------------------------------------- Sonraki / Önceki
    def next_item(self) -> Optional[MediaItem]:
        if not self._items:
            return None

        if self._mode == PlayMode.REPEAT_ONE:
            return self.current_item()

        if self._mode == PlayMode.SHUFFLE:
            if not self._shuffle_order or len(self._shuffle_order) != len(self._items):
                self._rebuild_shuffle_order()
            self._shuffle_pos += 1
            if self._shuffle_pos >= len(self._shuffle_order):
                if self._mode == PlayMode.REPEAT_ALL:
                    self._rebuild_shuffle_order()
                    self._shuffle_pos = 0
                else:
                    return None
            next_idx = self._shuffle_order[self._shuffle_pos]
            self.set_current_index(next_idx)
            return self.current_item()

        # Sıralı veya Repeat All / Stop After
        next_idx = self._current_index + 1
        if next_idx >= len(self._items):
            if self._mode == PlayMode.REPEAT_ALL:
                next_idx = 0
            else:
                return None  # Stop after veya liste sonu

        self.set_current_index(next_idx)
        return self.current_item()

    def previous_item(self) -> Optional[MediaItem]:
        if not self._items:
            return None

        if self._mode == PlayMode.REPEAT_ONE:
            return self.current_item()

        if self._mode == PlayMode.SHUFFLE:
            if self._shuffle_pos > 0:
                self._shuffle_pos -= 1
                next_idx = self._shuffle_order[self._shuffle_pos]
                self.set_current_index(next_idx)
                return self.current_item()
            return self.current_item()

        prev_idx = self._current_index - 1
        if prev_idx < 0:
            if self._mode == PlayMode.REPEAT_ALL:
                prev_idx = len(self._items) - 1
            else:
                prev_idx = 0

        self.set_current_index(prev_idx)
        return self.current_item()

    # ---------------------------------------------------------------- Liste Yönetimi
    def add_items(self, items: List[MediaItem]) -> None:
        if not items:
            return
        self._items.extend(items)
        if self._mode == PlayMode.SHUFFLE:
            self._rebuild_shuffle_order()
        self.itemsChanged.emit()

    def insert_items(self, index: int, items: List[MediaItem]) -> None:
        idx = max(0, min(len(self._items), index))
        for i, item in enumerate(items):
            self._items.insert(idx + i, item)
        if self._current_index >= idx:
            self._current_index += len(items)
        if self._mode == PlayMode.SHUFFLE:
            self._rebuild_shuffle_order()
        self.itemsChanged.emit()

    def remove_item(self, index: int) -> None:
        if 0 <= index < len(self._items):
            del self._items[index]
            if self._current_index == index:
                if self._current_index >= len(self._items):
                    self._current_index = len(self._items) - 1
                self.currentIndexChanged.emit(self._current_index)
            elif self._current_index > index:
                self._current_index -= 1
                self.currentIndexChanged.emit(self._current_index)
            if self._mode == PlayMode.SHUFFLE:
                self._rebuild_shuffle_order()
            self.itemsChanged.emit()

    def clear(self) -> None:
        self._items.clear()
        self._current_index = -1
        self._shuffle_order.clear()
        self._shuffle_pos = -1
        self.currentIndexChanged.emit(-1)
        self.itemsChanged.emit()

    def move_item(self, from_idx: int, to_idx: int) -> None:
        if 0 <= from_idx < len(self._items) and 0 <= to_idx < len(self._items):
            item = self._items.pop(from_idx)
            self._items.insert(to_idx, item)
            if self._current_index == from_idx:
                self._current_index = to_idx
            elif from_idx < self._current_index <= to_idx:
                self._current_index -= 1
            elif to_idx <= self._current_index < from_idx:
                self._current_index += 1
            self.itemsChanged.emit()

    # ---------------------------------------------------------------- Sıralama
    def sort_by_name(self) -> None:
        cur_item = self.current_item()
        self._items.sort(key=lambda x: natural_sort_key(x.title))
        if cur_item:
            try:
                self._current_index = self._items.index(cur_item)
            except ValueError:
                pass
        self.itemsChanged.emit()

    def sort_by_date(self) -> None:
        cur_item = self.current_item()
        def _get_mtime(item: MediaItem):
            try:
                return os.path.getmtime(item.path)
            except OSError:
                return 0
        self._items.sort(key=_get_mtime, reverse=True)
        if cur_item:
            try:
                self._current_index = self._items.index(cur_item)
            except ValueError:
                pass
        self.itemsChanged.emit()

    def sort_by_size(self) -> None:
        cur_item = self.current_item()
        def _get_size(item: MediaItem):
            try:
                return os.path.getsize(item.path)
            except OSError:
                return 0
        self._items.sort(key=_get_size, reverse=True)
        if cur_item:
            try:
                self._current_index = self._items.index(cur_item)
            except ValueError:
                pass
        self.itemsChanged.emit()
