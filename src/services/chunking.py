import re

from src.models.domain import ChunkInput


class TextChunker:
    def __init__(self, size: int = 800, overlap: int = 120) -> None:
        if overlap >= size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.size, self.overlap = size, overlap

    def split(self, text: str, metadata: dict | None = None) -> list[ChunkInput]:
        clean = re.sub(r"\s+", " ", text).strip()
        if not clean:
            return []
        result, start, index = [], 0, 0
        while start < len(clean):
            end = min(start + self.size, len(clean))
            if end < len(clean):
                boundary = clean.rfind(" ", start + self.size // 2, end)
                end = boundary if boundary > start else end
            result.append(ChunkInput(clean[start:end].strip(), index, metadata or {}))
            if end == len(clean):
                break
            start, index = end - self.overlap, index + 1
        return result

