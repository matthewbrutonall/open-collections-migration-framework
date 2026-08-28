from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from enum import Enum

class EntityType(str, Enum):
    DESCRIPTION = "description"
    AGENT = "agent"
    REPOSITORY = "repository"
    TERM = "term"
    ACCESSION = "accession"
    INSTANTIATION = "instantiation"

class RelationType(str, Enum):
    CHILD_OF = "child_of"
    HELD_BY = "held_by"
    CREATED_BY = "created_by"
    ACCUMULATED_BY = "accumulated_by"
    SUBJECT_AGENT = "subject_agent"
    ACQUIRED_FROM = "acquired_from"
    ACCESSIONED_AS = "accessioned_as"
    HAS_SUBJECT = "has_subject"
    HAS_PLACE = "has_place"
    HAS_GENRE = "has_genre"
    HAS_OBJECT_NAME = "has_object_name"
    HAS_INSTANTIATION = "has_instantiation"

@dataclass
class Identifier:
    value: str
    kind: str
    source_field: Optional[str] = None

@dataclass
class DateValue:
    expression: str
    begin: Optional[str] = None
    end: Optional[str] = None
    schema: Optional[str] = None
    certainty: Optional[str] = None
    inferred: bool = False

@dataclass
class Entity:
    id: str
    type: EntityType
    identifiers: List[Identifier] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Edge:
    source_id: str
    target_id: str
    relation: RelationType
    properties: Dict[str, Any] = field(default_factory=dict)
