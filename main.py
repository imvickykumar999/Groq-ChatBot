from groq import Groq

client = Groq(api_key='gsk_5rPxxxxxxxxxxxxxxxxxxxxxxxxxxxxxw9RPf')

# Provide at least one message for the conversation.
messages = [
    {"role": "user", "content": "Hello, how are you?"}
]

response = client.chat.completions.create(
    model="qwen-2.5-32b",
    messages=messages,
    temperature=0.6,
    max_tokens=4096,  # Changed parameter name to max_tokens.
    top_p=0.95,
    stream=True,
)

for chunk in response:
    # Use .get() in case 'content' is missing in delta.
    content = getattr(chunk.choices[0].delta, "content", "")
    print(content, end="")
