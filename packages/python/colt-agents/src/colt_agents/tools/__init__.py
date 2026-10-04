"""Concrete typed tools, built from application-layer use cases (CLAUDE.md §2.3, §16)."""

from colt_agents.tools.get_lead import GetLeadInput, GetLeadOutput, build_get_lead_tool

__all__ = ["GetLeadInput", "GetLeadOutput", "build_get_lead_tool"]
