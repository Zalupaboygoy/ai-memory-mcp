"""FastMCP application instance (tools register against this object)."""
from fastmcp import FastMCP

mcp = FastMCP(
    name="ai-memory",
    instructions="""
PostgreSQL + Neo4j hybrid KB + Gitea + local git tools.
Authoritative tool list, argument semantics, workflows: use the bundled project skill "ai-memory-mcp-neo4j-skill" dont read for_human.md.
Coarse order when exploring: get_structure → search / semantic_search → write_entry → update_summary → graph tools.
""",
)
