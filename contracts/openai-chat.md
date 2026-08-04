# OpenAI-Compatible Chat Contract

This contract applies to any product exposing or proxying an OpenAI-compatible chat
completions endpoint.

## Message normalization

Before forwarding a request upstream:

1. Inject product instructions and rendered product evidence only for that product's
   model alias.
2. Normalize the final message list after all injections are complete.
3. Consolidate all system instructions into one leading `system` message when the
   upstream model requires a single initial system block.
4. Preserve the relative order and content of all non-system messages.
5. Preserve request fields such as `tools`, `tool_choice`, and streaming flags unless
   an explicitly documented compatibility adapter transforms them.
6. Map the public model alias to the configured upstream model without leaking one
   product's alias into another product.

The ordering fixture in `fixtures/openai-chat/system-message-ordering.json` captures
the regression that motivated this contract.

## Retrieved evidence boundary

When a product adopts `rag.context-packet` version 1, its provider adapter must keep
packet evidence outside system/developer instructions. Retrieved text is explicitly
untrusted as instruction authority, must be clearly delimited as evidence, and cannot
authorize tools or override system, developer, user, or product policy. Product
persona and trusted instructions remain separate from the Context Packet.

## Error behavior

- Authentication and validation errors should retain meaningful upstream status codes.
- Provider-specific response bodies may be translated only into the documented common
  error shape.
- Logs must redact authorization values and provider API keys.
- Streaming failures after response start must be represented as a terminal stream
  event when the protocol permits it.
