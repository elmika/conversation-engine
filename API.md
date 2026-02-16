# API usage

How to call the conversation endpoints. The app must be running (e.g. `uvicorn app.main:app` or Docker on port 8000). Conversation endpoints require `OPENAI_API_KEY` in the environment; health does not.

**Endpoints:** Health `GET /healthz` · Create + first turn `POST /conversations` · Append turn `POST /conversations/{id}` · Stream first turn `POST /conversations/stream` · Stream append `POST /conversations/{id}/stream`  
**Interactive docs:** http://127.0.0.1:8000/docs

---

## Example: create conversation and append turn

**Create** (non-streaming):

```bash
curl -X POST http://127.0.0.1:8000/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_slug": "default",
    "messages": [
      { "role": "user", "content": "Hello my name is John" }
    ]
  }'
```

Response:

```json
{
  "conversation_id": "abc123",
  "assistant_message": "...",
  "model": "gpt-4.1-mini",
  "timings": {
    "ttfb_ms": 0,
    "total_ms": 412
  }
}
```

**Append** a turn (reuse `conversation_id` from above):

```bash
curl -X POST http://127.0.0.1:8000/conversations/abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_slug": "default",
    "messages": [
      { "role": "user", "content": "Can you tell me my name?" }
    ]
  }'
```

For `POST /conversations/{conversation_id}`, the service automatically loads all previous `user` and `assistant` messages for that conversation and prepends them to the new `messages` you send before calling the model. You only need to send the **new** user turn(s); you do not need to resend history.

---

## Example: streaming (existing conversation)

Stream tokens for an **existing** conversation:

```bash
curl -N -X POST http://127.0.0.1:8000/conversations/abc123/stream \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_slug": "default",
    "messages": [
      { "role": "user", "content": "Stream a short answer." }
    ]
  }'
```

Server-Sent Events:

```text
event: meta
data: {"conversation_id":"...","model":"gpt-4.1-mini","prompt_slug":"default"}

event: chunk
data: {"delta":"First part ..."}

event: chunk
data: {"delta":"Next part ..."}

event: done
data: {"conversation_id":"...","assistant_message":"Full answer ...","model":"gpt-4.1-mini","timings":{"ttfb_ms":10,"total_ms":120}}
```

For `POST /conversations/{conversation_id}/stream`, the model sees the full conversation history (all previous `user` and `assistant` messages) plus the new `messages` you send in this request.

---

## Example: streaming first turn

Create a **new** conversation and stream the first response:

```bash
curl -N -X POST http://127.0.0.1:8000/conversations/stream \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_slug": "default",
    "messages": [
      { "role": "user", "content": "Stream from the very first message." }
    ]
  }'
```

SSE shape is the same (`meta`, `chunk`, `done`). The response includes a new `conversation_id` to reuse for append or stream-append.

---

## Quick command-line tests

Copy-paste from repo root. Replace `CONV_ID` with a real `conversation_id` where noted.

**Health (no API key)**

```bash
curl -s http://127.0.0.1:8000/healthz
# {"status":"ok"}
```

**Request ID** (optional header; echoed in logs)

```bash
curl -s -H "X-Request-Id: my-test-123" http://127.0.0.1:8000/healthz
```

**Create conversation** (needs API key)

```bash
curl -s -X POST http://127.0.0.1:8000/conversations \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say hello in one word."}]}'
```

**Append turn** (use `conversation_id` from above)

```bash
curl -s -X POST http://127.0.0.1:8000/conversations/CONV_ID \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"What did you say?"}]}'
```

**Stream first turn** (needs API key; `-N` keeps connection open)

```bash
curl -N -s -X POST http://127.0.0.1:8000/conversations/stream \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Count to 3."}]}'
```

**Stream append**

```bash
curl -N -s -X POST http://127.0.0.1:8000/conversations/CONV_ID/stream \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Repeat that."}]}'
```

**Error handling** (404 for unknown path; 500 with optional `request_id` in body for unhandled errors)

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/nonexistent
# 404
```
