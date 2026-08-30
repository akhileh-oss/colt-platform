"""Repository and provider ports (CLAUDE.md §2.7, §5.2).

Interfaces the application layer depends on; `colt-db` and `colt-integrations` provide the
concrete implementations. Defined as `typing.Protocol`s rather than ABCs so an implementation
does not need to import this package to satisfy one — only structural compatibility is required.
"""
