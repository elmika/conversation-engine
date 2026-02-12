## Streaming – Risks and Future Improvements

- **OpenAI SDK streaming shape**  
  The adapter assumes `event.type == "response.output_text.delta"` and uses `event.delta`.  
  If the SDK changes event names or payload fields, we will need a small adjustment in `OpenAILLMAdapter.stream`.  
  Unit tests stay stable because they mock the adapter rather than hitting the real API.

- **Backpressure / long streams**  
  The current implementation streams tokens as they arrive with no explicit backpressure controls.  
  This is acceptable for a demo, but heavier workloads may require:  
  - Rate limiting or throttling of outbound SSE events.  
  - Chunk aggregation (buffering partial deltas) to reduce event volume.  
  - Timeouts or maximum stream durations to protect the service.

- **Error handling and non-happy-path events**  
  Non-happy-path streaming events (for example `response.failed`, `response.incomplete`) are not yet translated into SSE error events or a terminal `done` with an `error` field.  
  A next step would be to:  
  - Wrap adapter and OpenAI errors in a structured error payload.  
  - Emit a final `done` SSE event containing `error` information (alongside timings and model metadata).  
  - Optionally surface an `error` SSE event type for clients that want to differentiate failures from normal completion.

