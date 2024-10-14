COMPLETION_PROMPT_USER = """
{problem}

Please solve this problem step-by-step, boxing the final answer.
"""

COMPLETION_PROMPT_ASSISTANT = """
Certainly. Here is the step-by-step reasoning and final answer to the problem:

{prefix}
"""

RAW_COMPLETION_TEMPLATE = """<BOS_TOKEN><|START_OF_TURN_TOKEN|><|SYSTEM_TOKEN|><|END_OF_TURN_TOKEN|><|START_OF_TURN_TOKEN|><|USER_TOKEN|>{user_turn}<|END_OF_TURN_TOKEN|><|START_OF_TURN_TOKEN|><|CHATBOT_TOKEN|>{assistant_turn}"""
