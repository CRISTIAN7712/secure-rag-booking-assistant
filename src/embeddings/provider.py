from typing import Protocol, Sequence

import numpy as np
from numpy.typing import NDArray


class EmbeddingProvider(Protocol):
    model_name: str

    def encode(self, texts: Sequence[str]) -> NDArray[np.float32]: ...

