import json

transcript_path = "/home/codespace/.gemini/antigravity-cli/brain/d00d0aa6-5636-4f7a-a64f-8cfd12177b28/.system_generated/logs/transcript.jsonl"
with open(transcript_path) as f:
    lines = f.readlines()

for line in lines[-50:]:
    data = json.loads(line)
    if data["type"] == "PLANNER_RESPONSE":
        print(f"--- MODEL RESPONSE (Step {data['step_index']}) ---")
        if "content" in data and data["content"]:
            print(data["content"])
        if "tool_calls" in data:
            print("Tools:", data["tool_calls"])
        if "thinking" in data:
            print(data["thinking"])

