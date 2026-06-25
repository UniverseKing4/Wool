import asyncio
import json
from wool.providers.base import ToolCall

pending_tool_calls = [
    ToolCall(id="tc1", name="use_subagent", arguments=json.dumps({"tasks": ["Task 1", "Task 2"]})),
]

original_pending_tool_calls = pending_tool_calls
expanded_tool_calls = []
expansion_map = {}

for tc in pending_tool_calls:
    if tc.name == "use_subagent":
        try:
            args = json.loads(tc.arguments) if tc.arguments else {}
            tasks_array = args.get("tasks", [])
            if tasks_array and isinstance(tasks_array, list):
                expanded_ids = []
                for i, t in enumerate(tasks_array):
                    new_args = args.copy()
                    new_args.pop("tasks", None)
                    new_args["task"] = t
                    expanded_id = f"{tc.id}_{i}"
                    expanded_ids.append(expanded_id)
                    expanded_tool_calls.append(ToolCall(
                        id=expanded_id,
                        name="use_subagent",
                        arguments=json.dumps(new_args)
                    ))
                expansion_map[tc.id] = expanded_ids
                continue
        except Exception:
            pass
    expanded_tool_calls.append(tc)

pending_tool_calls = expanded_tool_calls

completed_results = {
    "tc1_0": "Output from subagent 1",
    "tc1_1": "Output from subagent 2"
}

for original_tc in original_pending_tool_calls:
    if original_tc.id in expansion_map:
        expanded_ids = expansion_map[original_tc.id]
        combined_result = []
        for i, exp_id in enumerate(expanded_ids):
            combined_result.append(f"--- Subagent {i+1} Output ---\n{completed_results.get(exp_id, '')}")
        final_result_text = "\n\n".join(combined_result)
    else:
        final_result_text = completed_results.get(original_tc.id, "")

    print(f"Original ID: {original_tc.id}")
    print(f"Content:\n{final_result_text}")

