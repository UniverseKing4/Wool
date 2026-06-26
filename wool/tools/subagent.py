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
                name="tasks",
                type="array",
                description="List of tasks to delegate concurrently. To spawn 3 subagents at once, provide an array of 3 distinct tasks.",
                required=False,
                items_type="string",
            ),
            ToolParameter(
                name="task",
                type="string",
                description="Legacy single task argument. Prefer 'tasks' for multiple concurrent subagents.",
                required=False,
            ),
            ToolParameter(
                name="context",
                type="string",
                description="Additional context to pass to the subagent.",
                required=False,
            ),
            ToolParameter(
                name="tools",
                type="array",
                description="List of tool names the subagent is allowed to use.",
                required=False,
                items_type="string",
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        task: str = kwargs.get("task", "")
        context: str = kwargs.get("context", "")
        tools: list[str] = kwargs.get("tools", [])

        # Note: 'tasks' array expansion is handled upstream in agent.py to preserve UI parallelism.
        # This execute method only handles single tasks.

        if not task:
            return ToolResult(
                success=False, output="", error="Task description is required."
            )

        import uuid

        from wool.agent import WoolAgent
        from wool.config import WoolConfig

        sub_config = WoolConfig.load()
        sub_config.active_session = f"subagent_{uuid.uuid4().hex[:8]}"
        sub_agent = WoolAgent(sub_config)

        # Prevent infinite subagent recursion
        sub_agent.tool_registry._tools.pop("use_subagent", None)

        # Restrict tools if specified, handling 'default_api:' prefixes
        if tools:
            clean_tools = [t.replace("default_api:", "") for t in tools]
            for name in list(sub_agent.tool_registry._tools.keys()):
                if name not in clean_tools:
                    sub_agent.tool_registry._tools.pop(name, None)

        prompt = f"TASK:\n{task}\n"
        if context:
            prompt += f"\nCONTEXT:\n{context}\n"

        final_output = ""
        try:
            # Consume the generator to drive the subagent forward
            async for _event_type, _content in sub_agent.process_input(prompt):
                pass

            if sub_agent.messages and sub_agent.messages[-1].role == "assistant":
                import re

                final_output = sub_agent.messages[-1].content or ""
                final_output = re.sub(
                    r"<think>.*?</think>", "", final_output, flags=re.DOTALL
                ).strip()
            else:
                final_output = "The subagent completed its execution but did not produce a final response."

        except Exception as exc:
            return ToolResult(
                success=False,
                output=f"Subagent execution failed: {exc}",
                error=str(exc),
            )
        finally:
            # Clean up the temporary session file
            path = sub_agent.get_session_path()
            if path.exists():
                path.unlink()

        return ToolResult(
            success=True,
            output=f"Subagent Execution Complete.\n\nFinal Output:\n{final_output}",
            metadata={"task": task, "tools": tools},
        )
