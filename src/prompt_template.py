TRANSLATE_BATCH_INSTRUCTION = (
    "Translate the provided text fields into {target_language}. "
    "Preserve meaning, named entities, numbers, negation, quantifiers, temporal cues, and inference-relevant details. "
    "Do not explain. Return only the JSON object required by the schema."
)

PASS_THROUGH_MESSAGE = (
    "OPENAI_API_KEY is missing. Translate these rows via ChatGPT web/MCP tools, "
    "then call write_dataset_output."
)
