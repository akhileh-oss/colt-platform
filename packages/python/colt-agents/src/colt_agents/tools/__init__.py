"""Concrete typed tools, built from application-layer use cases or provider ports (CLAUDE.md
§2.3, §16)."""

from colt_agents.tools.fetch_page import FetchPageInput, FetchPageOutput, build_fetch_page_tool
from colt_agents.tools.get_lead import GetLeadInput, GetLeadOutput, build_get_lead_tool
from colt_agents.tools.record_evidence import (
    RecordEvidenceInput,
    RecordEvidenceOutput,
    build_record_evidence_tool,
)
from colt_agents.tools.search_web import (
    SearchWebInput,
    SearchWebOutput,
    SearchWebResultItem,
    build_search_web_tool,
)

__all__ = [
    "FetchPageInput",
    "FetchPageOutput",
    "GetLeadInput",
    "GetLeadOutput",
    "RecordEvidenceInput",
    "RecordEvidenceOutput",
    "SearchWebInput",
    "SearchWebOutput",
    "SearchWebResultItem",
    "build_fetch_page_tool",
    "build_get_lead_tool",
    "build_record_evidence_tool",
    "build_search_web_tool",
]
