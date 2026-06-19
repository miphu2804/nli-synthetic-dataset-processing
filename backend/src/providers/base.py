import inspect

from fastmcp import FastMCP


class ToolProvider:
    """Base for MCP tool providers — auto-registers every @tool-marked method."""

    def register(self, mcp: FastMCP) -> None:
        for name, member in inspect.getmembers(type(self)):
            if hasattr(member, "__fastmcp__"):
                mcp.add_tool(getattr(self, name))

    @staticmethod
    def sample_range_to_offset_limit(
        from_sample: int,
        to_sample: int | None,
    ) -> tuple[int, int | None]:
        if to_sample is not None and to_sample < from_sample:
            raise ValueError("to_sample must be greater than or equal to from_sample.")
        row_offset = from_sample - 1
        row_limit = None if to_sample is None else to_sample - from_sample + 1
        return row_offset, row_limit
