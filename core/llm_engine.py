"""
Engine module for PCAgentJohnBot.

This module defines the Engine class, which serves as an abstraction layer over different language models (like GPT and Ollama). 
It provides a unified interface for invoking models, handling structured outputs with Pydantic models, and streaming responses. 
The Context class is also defined to manage conversation history in a structured way.
"""

import re
import os
import json
import time
import logging
from core.utils import load_env, is_openai_key_set
from pydantic import BaseModel
from datetime import datetime
from typing import Literal, Optional, List
import openai
from openai import OpenAI
from langchain_ollama import OllamaLLM
from langchain_core.messages import SystemMessage, AnyMessage

load_env()
# Import-time flag; pages can import this to know whether GPT is available.
# Use is_openai_key_set() for a live runtime check (reflects keys saved during the session).
OPENAI_KEY_CONFIGURED: bool = is_openai_key_set()

logger = logging.getLogger(__name__)

class Engine():
    GPT_MODELS = ["gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-5-mini"]
    OLLAMA_MODELS = ["qwen2.5:latest", "qwen3:4B", "qwen3:8B"]
    ALL_MODELS = GPT_MODELS + OLLAMA_MODELS
    def __init__(self, model: Optional[Literal["qwen2.5:latest", "qwen3:4B", "qwen3:8B", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-5-mini"]] = None, temperature: float = 0):
        self.model = model or "qwen2.5:latest"
        self.temperature = temperature
        self.engine = self.__start_engine()
    
    def __start_engine(self):
        logger.info(f"Starting engine with model: {self.model}")
        if self.model in self.GPT_MODELS:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not is_openai_key_set():
                raise ValueError(
                    f"GPT model '{self.model}' requires an OpenAI API key. "
                    "Please set OPENAI_API_KEY in your .env file."
                )
            logger.info("Initializing GPT model...")
            engine = OpenAI(api_key=api_key, max_retries=6)
        elif self.model in self.OLLAMA_MODELS:
            logger.info(f"Using Ollama LLM with model: {self.model}")
            engine = OllamaLLM(model=self.model)
            # Separate instance that forces Ollama into JSON-output mode
            self._ollama_json_engine = OllamaLLM(model=self.model, format="json")
        else:
            raise ValueError(f"Unsupported model: {self.model}")
        return engine
    
    def _convert_messages_to_openai(self, messages: List[AnyMessage]) -> List[dict]:
        """Convert LangChain messages to OpenAI format."""
        openai_messages = []
        for msg in messages:
            if msg.__class__.__name__ == 'SystemMessage':
                openai_messages.append({"role": "system", "content": msg.content})
            elif msg.__class__.__name__ == 'HumanMessage':
                openai_messages.append({"role": "user", "content": msg.content})
            elif msg.__class__.__name__ == 'AIMessage':
                openai_messages.append({"role": "assistant", "content": msg.content})
            else:
                # Default to user role for unknown message types
                openai_messages.append({"role": "user", "content": msg.content})
        return openai_messages
    
    def _format_tools_for_ollama(self, tools: List) -> str:
        """Convert OpenAI format tools to a text format for Ollama."""
        if not tools:
            return ""
        
        tools_text = "\n\nAvailable tools:\n"
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                name = func.get("name", "")
                description = func.get("description", "")
                params = func.get("parameters", {})
                
                tools_text += f"\n- {name}: {description}\n"
                if params.get("properties"):
                    tools_text += "  Parameters:\n"
                    for param_name, param_info in params["properties"].items():
                        param_type = param_info.get("type", "string")
                        param_desc = param_info.get("description", "")
                        tools_text += f"    - {param_name} ({param_type}): {param_desc}\n"
        
        return tools_text
    
    @staticmethod
    def _repair_json(text: str) -> str:
        """Best-effort JSON repair: truncate at the last valid top-level object close."""
        text = text.strip()
        # Strip markdown fences
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            text = text.strip()
        start = text.find('{')
        if start == -1:
            return text
        text = text[start:]
        # Walk forward counting braces; keep the outermost object
        depth = 0
        in_string = False
        escape = False
        end_idx = -1
        for i, ch in enumerate(text):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        if end_idx != -1:
            return text[:end_idx]
        # Incomplete JSON: try to close open braces
        return text + ('}' * depth)

    def _parse_tool_calls_from_response(self, response: str) -> Optional[dict]:
        """Try to parse tool calls from Ollama response."""
        try:
            # Look for JSON in the response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            # Check if this looks like a tool_calls response
            if data.get("type") == "tool_calls" and "tool_calls" in data:
                return data
        except (json.JSONDecodeError, AttributeError):
            pass
        
        return None
    
    @staticmethod
    def _call_with_backoff(fn, *args, max_attempts: int = 8, base_delay: float = 5.0, **kwargs):
        """Call *fn* with exponential backoff on RateLimitError / 429 responses."""
        for attempt in range(1, max_attempts + 1):
            try:
                return fn(*args, **kwargs)
            except openai.RateLimitError as exc:
                if attempt == max_attempts:
                    raise
                # Honour Retry-After header when present
                retry_after = None
                if hasattr(exc, 'response') and exc.response is not None:
                    retry_after = exc.response.headers.get('retry-after')
                if retry_after:
                    wait = float(retry_after) + 1.0
                else:
                    wait = base_delay * (2 ** (attempt - 1))  # 5, 10, 20, 40 …
                logger.warning(
                    f"[Engine] Rate-limited (attempt {attempt}/{max_attempts}). "
                    f"Waiting {wait:.1f}s before retry…"
                )
                time.sleep(wait)

    def invoke(self, 
               messages: List[AnyMessage], 
               base_model: Optional[BaseModel] = None,
               tools: Optional[List] = None):
        if self.model in self.GPT_MODELS:
            # Convert LangChain messages to OpenAI format
            openai_messages = self._convert_messages_to_openai(messages)
            
            if base_model:
                engine: OpenAI = self.engine
                kwargs = {
                    "messages": openai_messages,
                    "model": self.model,
                    "response_format": base_model
                }
                if tools:
                    kwargs["tools"] = tools
                response = self._call_with_backoff(
                    engine.beta.chat.completions.parse, **kwargs
                )
                return response.choices[0].message.parsed
            else:
                engine: OpenAI = self.engine
                kwargs = {
                    "messages": openai_messages,
                    "model": self.model,
                    "temperature": self.temperature
                }
                if tools:
                    kwargs["tools"] = tools
                response = self._call_with_backoff(
                    engine.chat.completions.create, **kwargs
                )
                
                # Handle tool calling
                if tools and response.choices[0].message.tool_calls:
                    return {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments
                                }
                            }
                            for tool_call in response.choices[0].message.tool_calls
                        ]
                    }
                
                return response.choices[0].message.content
        elif self.model in self.OLLAMA_MODELS:
            if base_model:
                # Add schema instruction to the message
                schema_str = base_model.model_json_schema()
                instruction = f"""
IMPORTANT: Respond with ONLY valid JSON, no other text.
Start with {{ and end with }}.
No markdown, explanations, or text before/after JSON.

Required schema:
{schema_str}

Output ONLY JSON:
"""
                
                if messages and isinstance(messages[0], SystemMessage):
                    messages[0].content += f"\n\n{instruction}"
                else:
                    schema_message = SystemMessage(content=instruction)
                    messages = [schema_message] + messages
            elif tools:
                # Add tools instruction to the message
                tools_text = self._format_tools_for_ollama(tools)
                tool_instruction = f"""{tools_text}

When you need to use a tool, respond with a JSON object in this format (and NOTHING else):
{{
  "type": "tool_calls",
  "tool_calls": [
    {{
      "id": "call_<number>",
      "function": {{
        "name": "<tool_name>",
        "arguments": "<JSON string with tool arguments>"
      }}
    }}
  ]
}}

For example:
{{"type": "tool_calls", "tool_calls": [{{"id": "call_1", "function": {{"name": "get_weather", "arguments": "{{\\"location\\": \\"San Francisco, CA\\"}}"}}}}]}}

If the user's request doesn't require tools, respond naturally."""
                
                if messages and isinstance(messages[0], SystemMessage):
                    messages[0].content += f"\n\n{tool_instruction}"
                else:
                    tool_message = SystemMessage(content=tool_instruction)
                    messages = [tool_message] + messages
            
            # Use the JSON-mode engine for structured output to force valid JSON
            _invoke_engine = self._ollama_json_engine if base_model and hasattr(self, '_ollama_json_engine') else self.engine
            response = _invoke_engine.invoke(messages)
            
            if base_model:
                import json
                import re
                
                logger.debug(f"[ENGINE] Raw Ollama response: {repr(response)}")
                
                # Try to parse the response
                if not response or not response.strip():
                    logger.error(f"[ENGINE] Ollama returned empty response for structured output")
                    raise ValueError("Ollama model returned empty response")
                
                # First, try direct JSON parsing
                try:
                    parsed = base_model.model_validate_json(response)
                    logger.debug("[ENGINE] Successfully parsed response with model_validate_json")
                    return parsed
                except Exception as e:
                    logger.debug(f"[ENGINE] model_validate_json failed: {e}")
                
                # Try to repair and re-parse
                error_message = None
                try:
                    repaired = self._repair_json(response)
                    logger.debug(f"[ENGINE] Repaired JSON: {repr(repaired)}")
                    parsed = json.loads(repaired)
                    result = base_model(**parsed)
                    logger.debug("[ENGINE] Successfully parsed repaired JSON")
                    return result
                except Exception as e:
                    error_message = str(e)
                    logger.debug(f"[ENGINE] JSON repair/parsing failed: {error_message}")
                
                # If all else fails, log the response and raise error
                logger.error(f"[ENGINE] Could not parse response. Raw: {repr(response)}")
                raise ValueError(f"Failed to parse Ollama response as JSON: {error_message}")
            elif tools:
                # Check if response contains tool calls
                tool_calls = self._parse_tool_calls_from_response(response)
                if tool_calls:
                    logger.debug(f"[ENGINE] Parsed tool calls from Ollama response")
                    return tool_calls
                else:
                    logger.debug(f"[ENGINE] No tool calls detected, returning as regular response")
                    return response
            
            return response
        else:
            raise NotImplementedError("Parsing response into structured data is not implemented yet.")
    
    async def async_invoke(self, 
                           messages: List[AnyMessage], 
                           base_model: Optional[BaseModel] = None, 
                           tools: Optional[List] = None):
        if self.model in self.GPT_MODELS:
            openai_messages = self._convert_messages_to_openai(messages)
            
            if base_model:
                raise NotImplementedError("Async structured output is not implemented for GPT models yet.")
            else:
                engine: OpenAI = self.engine
                kwargs = {
                    "messages": openai_messages,
                    "model": self.model,
                    "temperature": self.temperature
                }
                if tools:
                    kwargs["tools"] = tools
                response = await engine.chat.completions.create(**kwargs)
                
                # Handle tool calling
                if tools and response.choices[0].message.tool_calls:
                    return {
                        "type": "tool_calls",
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments
                                }
                            }
                            for tool_call in response.choices[0].message.tool_calls
                        ]
                    }
                
                return response.choices[0].message.content
        elif self.model in self.OLLAMA_MODELS:
            if base_model:
                if messages and isinstance(messages[0], SystemMessage):
                    messages[0].content += f"\n\nFinal Output Schema:\n{base_model.model_json_schema()}"
                else:
                    schema_message = SystemMessage(content=f"Final Output Schema:\n{base_model.model_json_schema()}")
                    messages = [schema_message] + messages
            elif tools:
                # Add tools instruction to the message
                tools_text = self._format_tools_for_ollama(tools)
                tool_instruction = f"""{tools_text}

When you need to use a tool, respond with a JSON object in this format (and NOTHING else):
{{
  "type": "tool_calls",
  "tool_calls": [
    {{
      "id": "call_<number>",
      "function": {{
        "name": "<tool_name>",
        "arguments": "<JSON string with tool arguments>"
      }}
    }}
  ]
}}

If the user's request doesn't require tools, respond naturally."""
                
                if messages and isinstance(messages[0], SystemMessage):
                    messages[0].content += f"\n\n{tool_instruction}"
                else:
                    tool_message = SystemMessage(content=tool_instruction)
                    messages = [tool_message] + messages
            
            response = await self.engine.async_invoke(messages)
            
            if tools:
                # Check if response contains tool calls
                tool_calls = self._parse_tool_calls_from_response(response)
                if tool_calls:
                    logger.debug(f"[ENGINE] Parsed tool calls from async Ollama response")
                    return tool_calls
            
            return response
        else:
            raise NotImplementedError("Async invocation is not implemented for this model.")

    def stream(self, messages: List[AnyMessage], base_model: Optional[BaseModel] = None, tools: Optional[List] = None):
        if self.model in self.GPT_MODELS:
            # Convert LangChain messages to OpenAI format
            openai_messages = self._convert_messages_to_openai(messages)
            
            if base_model:
                # OpenAI streaming with structured output requires collecting the full message first
                engine: OpenAI = self.engine
                kwargs = {
                    "messages": openai_messages,
                    "model": self.model,
                    "response_format": base_model
                }
                if tools:
                    kwargs["tools"] = tools
                response = engine.beta.chat.completions.parse(**kwargs)
                yield response.choices[0].message.parsed
            else:
                kwargs = {
                    "messages": openai_messages,
                    "model": self.model,
                    "stream": True,
                    "temperature": self.temperature
                }
                if tools:
                    kwargs["tools"] = tools
                response = self.engine.chat.completions.create(**kwargs)
                
                # Accumulate response for tool call handling
                accumulated_content = ""
                tool_calls_data = {}
                
                for chunk in response:
                    delta = chunk.choices[0].delta
                    
                    # Accumulate content
                    if delta.content:
                        accumulated_content += delta.content
                        yield delta.content
                    
                    # Handle tool calls in streaming
                    if delta.tool_calls:
                        for tool_call in delta.tool_calls:
                            if tool_call.index not in tool_calls_data:
                                tool_calls_data[tool_call.index] = {
                                    "id": tool_call.id,
                                    "function": {"name": "", "arguments": ""}
                                }
                            if tool_call.function.name:
                                tool_calls_data[tool_call.index]["function"]["name"] += tool_call.function.name
                            if tool_call.function.arguments:
                                tool_calls_data[tool_call.index]["function"]["arguments"] += tool_call.function.arguments
                
                # Yield tool calls if they exist and no content was generated
                if tools and tool_calls_data and not accumulated_content:
                    yield {
                        "type": "tool_calls",
                        "tool_calls": list(tool_calls_data.values())
                    }
        elif self.model in self.OLLAMA_MODELS:
            if base_model:
                # Add schema instruction to the message
                schema_str = base_model.model_json_schema()
                instruction = f"""You MUST respond with valid JSON matching this schema:
{schema_str}

Important: Your response must be ONLY valid JSON, starting with {{ and ending with }}, with no additional text before or after."""
                
                if messages and isinstance(messages[0], SystemMessage):
                    messages[0].content += f"\n\n{instruction}"
                else:
                    schema_message = SystemMessage(content=instruction)
                    messages = [schema_message] + messages
                
                # Accumulate chunks and parse into base_model
                full_response = ""
                for chunk in self.engine.stream(messages):
                    full_response += chunk
                
                import json
                import re
                
                if not full_response or not full_response.strip():
                    logger.error(f"[ENGINE] Ollama returned empty response for structured output")
                    raise ValueError("Ollama model returned empty response")
                
                # First, try direct JSON parsing
                try:
                    yield base_model.model_validate_json(full_response)
                except Exception as e:
                    logger.debug(f"[ENGINE] model_validate_json failed: {e}")
                    
                    # Try to extract JSON from the response
                    try:
                        json_match = re.search(r'\{.*\}', full_response, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            logger.debug(f"[ENGINE] Extracted JSON: {json_str}")
                            parsed = json.loads(json_str)
                            yield base_model(**parsed)
                        else:
                            raise ValueError("No JSON found in response")
                    except Exception as e2:
                        logger.error(f"[ENGINE] JSON extraction failed: {e2}. Response: {repr(full_response)}")
                        raise ValueError(f"Failed to parse Ollama response as JSON: {e2}")
            elif tools:
                # Add tools instruction to the message
                tools_text = self._format_tools_for_ollama(tools)
                tool_instruction = f"""{tools_text}

When you need to use a tool, respond with a JSON object in this format (and NOTHING else):
{{
  "type": "tool_calls",
  "tool_calls": [
    {{
      "id": "call_<number>",
      "function": {{
        "name": "<tool_name>",
        "arguments": "<JSON string with tool arguments>"
      }}
    }}
  ]
}}

For example:
{{"type": "tool_calls", "tool_calls": [{{"id": "call_1", "function": {{"name": "get_weather", "arguments": "{{\\"location\\": \\"San Francisco, CA\\"}}"}}}}]}}

If the user's request doesn't require tools, respond naturally."""
                
                if messages and isinstance(messages[0], SystemMessage):
                    messages[0].content += f"\n\n{tool_instruction}"
                else:
                    tool_message = SystemMessage(content=tool_instruction)
                    messages = [tool_message] + messages
                
                # Accumulate chunks and check for tool calls
                full_response = ""
                for chunk in self.engine.stream(messages):
                    full_response += chunk
                    yield chunk
                
                # After streaming completes, check if response contains tool calls
                tool_calls = self._parse_tool_calls_from_response(full_response)
                if tool_calls:
                    logger.debug(f"[ENGINE] Detected tool calls in streamed response")
                    yield tool_calls
            else:
                for chunk in self.engine.stream(messages):
                    yield chunk
        else:
            raise NotImplementedError("Streaming is not implemented for this model.")

class Context(BaseModel):
    title: Optional[str] = None
    messages: List[AnyMessage] = []
    
    def __init__(self):
        super().__init__(
            title=datetime.now().strftime("Conversation on %Y-%m-%d at %H:%M:%S"),
            messages=[]
        )
    
    def __getitem__(self, key: int) -> AnyMessage:
        return self.messages[key]

    def __add__(self, message: AnyMessage) -> 'Context':
        self.messages = self.messages + [message]
        return self

    def __str__(self):
        context_str = f"{self.title}\n"
        context_str += "\n".join([f"{type(msg).__name__}: {msg.content}" for msg in self.messages])
        return context_str

    def append(self, message: AnyMessage) -> None:
        """Add a message to the conversation history."""
        self.messages.append(message)
    
    def extend(self, messages: List[AnyMessage]) -> None:
        """Add multiple messages to the conversation history."""
        self.messages.extend(messages)
    
    def clear(self) -> None:
        """Clear the conversation history."""
        self.messages = []

if __name__ == "__main__":
    engine = Engine(model="qwen3:4B")  # change to a GPT model if you want to test GPT features
    # test simple invocation
    print("#" + "-"*50 + "#")
    print("Testing simple invocation...")
    response = engine.invoke([SystemMessage(content="Hello, how are you?")])
    print("Response:", response)

    # test streaming
    print("#" + "-"*50 + "#")
    print("Streaming response:")
    for chunk in engine.stream([SystemMessage(content="Tell me a joke and stream the response.")]):
        print(chunk, end="", flush=True)
    print()

    # test with base model
    print("#" + "-"*50 + "#")
    class JokeResponse(BaseModel):
        joke: str
        length: int
    response_with_schema = engine.invoke(
        [SystemMessage(content="Tell me a joke and respond in the specified schema.")],
        base_model=JokeResponse
    )
    print("Response with schema:", response_with_schema)

    # test streaming with base model
    print("#" + "-"*50 + "#")
    print("Streaming response with schema:")
    for chunk in engine.stream(
        [SystemMessage(content="Tell me a joke and respond in the specified schema.")],
        base_model=JokeResponse
    ):
        print("Received chunk:", chunk)

    # test with tool calling (GPT only)
    print("#" + "-"*50 + "#")
    print("Testing invoke with tool calling (requires GPT model)...")
    gpt_engine = Engine(model="qwen2.5:latest")  # change to a GPT model if you want to test GPT tool calling
    
    # Mock MCP tools in OpenAI format
    mock_tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA"
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "Get the current time in a specific timezone",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "The timezone, e.g. America/New_York"
                        }
                    },
                    "required": ["timezone"]
                }
            }
        }
    ]
    
    try:
        # Invoke with tools - model should decide to use tools or respond naturally
        response = gpt_engine.invoke(
            [SystemMessage(content="What's the weather like in San Francisco?")],
            tools=mock_tools
        )
        print("Response with tools:", response)
        
        # Check if tool calls were made
        if isinstance(response, dict) and response.get("type") == "tool_calls":
            print(f"Model decided to call tools!")
            for tool_call in response["tool_calls"]:
                print(f"  - Tool: {tool_call['function']['name']}")
                print(f"    Arguments: {tool_call['function']['arguments']}")
        else:
            print(f"Model responded with text: {response[:100]}...")
    except Exception as e:
        print(f"Note: Tool calling test skipped (requires valid OpenAI API key): {e}")

    # test with tool calling (Ollama)
    print("#" + "-"*50 + "#")
    print("Testing invoke with tool calling (Ollama model)...")
    try:
        response = engine.invoke(
            [SystemMessage(content="What's the weather like in San Francisco and the current time in New York?")],
            tools=mock_tools
        )
        print("Response with tools:", response)
        
        # Check if tool calls were made
        if isinstance(response, dict) and response.get("type") == "tool_calls":
            print(f"Model decided to call tools!")
            for tool_call in response["tool_calls"]:
                print(f"  - Tool: {tool_call['function']['name']}")
                print(f"    Arguments: {tool_call['function']['arguments']}")
        else:
            print(f"Model responded with text: {response[:100]}...")
    except Exception as e:
        print(f"Note: Tool calling test failed: {e}")

    # test streaming with tools (GPT only)
    print("#" + "-"*50 + "#")
    print("Testing stream with tool calling (requires GPT model)...")
    try:
        print("Streaming response with tools:")
        for chunk in gpt_engine.stream(
            [SystemMessage(content="What time is it in Tokyo?")],
            tools=mock_tools
        ):
            if isinstance(chunk, dict) and chunk.get("type") == "tool_calls":
                print(f"\nModel called tools in stream!")
                for tool_call in chunk["tool_calls"]:
                    print(f"  - Tool: {tool_call['function']['name']}")
                    print(f"    Arguments: {tool_call['function']['arguments']}")
            else:
                print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"Note: Stream with tools test skipped (requires valid OpenAI API key): {e}")

    # test streaming with tools (Ollama)
    print("#" + "-"*50 + "#")
    print("Testing stream with tool calling (Ollama model)...")
    try:
        print("Streaming response with tools:")
        for chunk in engine.stream(
            [SystemMessage(content="What time is it in Tokyo and what's the weather in Paris?")],
            tools=mock_tools
        ):
            if isinstance(chunk, dict) and chunk.get("type") == "tool_calls":
                print(f"\nModel called tools in stream!")
                for tool_call in chunk["tool_calls"]:
                    print(f"  - Tool: {tool_call['function']['name']}")
                    print(f"    Arguments: {tool_call['function']['arguments']}")
            else:
                print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"Note: Stream with tools test failed: {e}")