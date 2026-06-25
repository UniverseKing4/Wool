"""use_subagent — delegate tasks to specialised sub-agents.

This module defines the tool schema so LLMs can request subagent
delegation.  The actual orchestration is handled by the agent core;
this tool returns an acknowledgement and architectural placeholder.
"""

from __future__ import annotations

from typing import Any

from wool.tools.base import Tool, ToolParameter, ToolResult


class SubagentDelegation(Tool):
    """Spin up a specialised subagent for parallel task execution."""

    @property
    def name(self) -> str:
        return "use_subagent"

    @property
    def description(self) -> str:
        return (
            "Delegate a task to a specialised subagent that can work in "
            "parallel. Specify the task description, optional context, and "
            "which tools the subagent may use."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="task", type="string",
                description="Description of the task for the subagent.",
            ),
            ToolParameter(
                name="context", type="string",
                description="Additional context to pass to the subagent.",
                required=False,
            ),
            ToolParameter(
                name="tools", type="array",
                description="List of tool names the subagent is allowed to use.",
                required=False,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        task: str = kwargs.get("task", "")
        context: str = kwargs.get("context", "")
        tools: list[str] = kwargs.get("tools", [])

        if not task:
            return ToolResult(success=False, output="", error="Task description is required.")

        # In the current release the subagent infrastructure is wired at the
        # agent-core level.  This tool records the request and returns
        # an acknowledgement so the LLM can continue its reasoning.
        summary = (
            f"Subagent request registered.\n"
            f"  Task: {task}\n"
        )
        if context:
            summary += f"  Context: {context[:200]}\n"
        if tools:
            summary += f"  Tools: {', '.join(tools)}\n"
        summary += (
            "\nNote: Subagent orchestration will execute this task in the "
            "background. Results will be provided when available."
        )
        return ToolResult(
            success=True,
            output=summary,
            metadata={"task": task, "tools": tools},
        )
