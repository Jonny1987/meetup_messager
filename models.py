from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: str
    name: str


@dataclass(frozen=True)
class Group:
    url_name: str
    name: str
