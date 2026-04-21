# Adding a new LLM provider

1. Create `src/agent_eval_hub/adapters/<name>.py` subclassing `Adapter`:
   ```python
   from .base import Adapter, AgentResponse, Tool, ToolCall

   class MyAdapter(Adapter):
       provider = "myprov"

       def __init__(self, model: str):
           super().__init__(model)
           # Construct the SDK client here.

       def complete(self, system, messages, tools=None, temperature=0.0) -> AgentResponse:
           # Call the provider, normalize to AgentResponse.
           ...
   ```

2. Register it in `src/agent_eval_hub/adapters/__init__.py`:
   ```python
   KNOWN_PROVIDERS = (..., "myprov")

   def get_adapter(name: str, model: str) -> Adapter:
       ...
       if name == "myprov":
           from .my import MyAdapter
           return MyAdapter(model=model)
   ```

3. Add pricing in `src/agent_eval_hub/pricing.py` (optional — unknown models get $0):
   ```python
   DEFAULT_PRICES["myprov-model"] = (1.00, 5.00)
   ```

4. Add to the dispatch table in `tests/contract/test_adapter_contract.py`:
   ```python
   _PROVIDER_CLASSES["myprov"] = ("agent_eval_hub.adapters.my", "MyAdapter")
   ```

5. Run `pytest tests/contract/` — every new provider must pass the three contract tests automatically.

No existing suite needs to change. `agent-eval --provider myprov --model ...` works immediately.
