from __future__ import annotations

from typing import Literal, NotRequired, TypedDict, Union


StatusUploaded = Literal["uploaded"]
StatusFailed = Literal["failed"]
StatusMovedRaw = Literal["moved_raw"]
StatusQueuedJpg = Literal["queued_jpg"]


class UploadedRecord(TypedDict):
    status: StatusUploaded
    path: str


class FailedRecord(TypedDict):
    status: StatusFailed
    path: str
    reason: str


class MovedRawRecord(TypedDict):
    status: StatusMovedRaw
    path: str


class QueuedJpgRecord(TypedDict):
    status: StatusQueuedJpg
    path: str


StateRecord = Union[UploadedRecord, FailedRecord, MovedRawRecord, QueuedJpgRecord]
StateDict = dict[str, StateRecord]


def is_uploaded(rec: StateRecord) -> bool:
    return rec.get("status") == "uploaded"
