"""Transport-independent client for RPent's SAM3 segmentation service."""

from __future__ import annotations

import base64
import hashlib
import io
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import imageio.v2 as imageio
import numpy as np

from rpent.utils.rpc import RpcClient, RpcError


@dataclass(frozen=True)
class Sam3Result:
    """One top-ranked SAM3 segmentation result."""

    found: bool
    score: float | None = None
    box: list[float] | None = None
    mask: np.ndarray | None = None
    mask_shape: tuple[int, int] | None = None
    reason: str | None = None


class Sam3Client:
    """Client wrapping the SAM3 service over any :class:`RpcClient`."""

    _IMAGE_ID_CACHE_SIZE = 2

    def __init__(self, client: RpcClient, *, timeout_s: float = 120.0) -> None:
        self._client = client
        self._timeout_s = timeout_s
        self._known_image_ids: OrderedDict[str, None] = OrderedDict()

    def segment(
        self,
        image: bytes | bytearray | memoryview | np.ndarray,
        *,
        text_prompt: str | None = None,
        point: list[int] | None = None,
        min_score: float = 0.2,
    ) -> Sam3Result:
        """Segment an image using exactly one text prompt or positive point.

        Point coordinates use RPent's image convention: ``[row, col]``.
        """
        prompt = text_prompt.strip() if isinstance(text_prompt, str) else None
        has_text = bool(prompt)
        has_point = point is not None
        if has_text == has_point:
            raise ValueError("segment requires exactly one of text_prompt or point")
        if has_point and (not isinstance(point, list) or len(point) != 2):
            raise ValueError("point must be [row, col]")
        if not 0.0 <= float(min_score) <= 1.0:
            raise ValueError("min_score must be between 0 and 1")

        if isinstance(image, np.ndarray):
            buffer = io.BytesIO()
            imageio.imwrite(buffer, image, format="png")
            image_bytes = buffer.getvalue()
        else:
            image_bytes = bytes(image)
        image_id = hashlib.sha256(image_bytes).hexdigest()
        body: dict[str, Any] = {"min_score": float(min_score)}
        if image_id in self._known_image_ids:
            self._known_image_ids.move_to_end(image_id)
            body["image_id"] = image_id
        else:
            body["image_base64"] = base64.b64encode(image_bytes).decode("ascii")
        if has_text:
            body["text_prompt"] = prompt
        else:
            body["point"] = [int(point[0]), int(point[1])]

        try:
            payload = self._client.call(
                "segment", kwargs=body, timeout_s=self._timeout_s
            )
        except RpcError as exc:
            if "image_id" not in body or "unknown image_id:" not in str(exc):
                raise
            body.pop("image_id")
            body["image_base64"] = base64.b64encode(image_bytes).decode("ascii")
            payload = self._client.call(
                "segment", kwargs=body, timeout_s=self._timeout_s
            )
        result = self._decode_result(payload)
        if "image_base64" in body:
            self._known_image_ids[image_id] = None
            if len(self._known_image_ids) > self._IMAGE_ID_CACHE_SIZE:
                self._known_image_ids.popitem(last=False)
        return result

    @staticmethod
    def _decode_result(payload: Any) -> Sam3Result:
        if not isinstance(payload, dict) or not isinstance(payload.get("found"), bool):
            raise RuntimeError(f"invalid SAM3 segment response: {payload!r}")

        score = payload.get("score")
        if score is not None:
            score = float(score)
        box = payload.get("box")
        if box is not None:
            if not isinstance(box, list) or len(box) != 4:
                raise RuntimeError(f"invalid SAM3 box: {box!r}")
            box = [float(value) for value in box]

        if not payload["found"]:
            return Sam3Result(
                found=False,
                score=score,
                box=box,
                reason=str(payload.get("reason") or "SAM3 found no mask"),
            )

        encoded_mask = payload.get("mask_png_base64")
        shape = payload.get("mask_shape")
        if not isinstance(encoded_mask, str) or not encoded_mask:
            raise RuntimeError("SAM3 response marked found but omitted mask_png_base64")
        if (
            not isinstance(shape, list)
            or len(shape) != 2
            or not all(isinstance(value, int) and value > 0 for value in shape)
        ):
            raise RuntimeError(f"invalid SAM3 mask_shape: {shape!r}")

        try:
            raw = base64.b64decode(encoded_mask, validate=True)
            decoded = np.asarray(imageio.imread(io.BytesIO(raw)))
        except Exception as exc:
            raise RuntimeError(f"could not decode SAM3 PNG mask: {exc}") from exc
        if decoded.ndim == 3:
            decoded = decoded[..., 0]
        expected_shape = (shape[0], shape[1])
        if decoded.shape != expected_shape:
            raise RuntimeError(
                "SAM3 mask shape mismatch: "
                f"response={expected_shape}, decoded={decoded.shape}"
            )

        mask = decoded > 0
        return Sam3Result(
            found=True,
            score=score,
            box=box,
            mask=mask,
            mask_shape=expected_shape,
        )
