from agentmap.services.llm_service import LLMService
from agentmap.exceptions import LLMProviderError

class DummyCfg:
    def __init__(self): pass

class DummyLogger:
    def get_class_logger(self, *_): return self
    def debug(self,*a,**k): pass
    def info(self,*a,**k): pass
    def warning(self,*a,**k): pass
    def error(self,*a,**k): pass

class DummyRouting:
    def select_candidates(self, _ctx):
        return [
            {"provider":"anthropic","model":"claude-3-5-sonnet"},
            {"provider":"openai","model":"gpt-4o"},
        ]

class Svc(LLMService):
    # override direct call for test determinism
    seq = []
    def _call_llm_direct(self, provider, messages, model, **_):
        self.seq.append((provider, model))
        if provider == "anthropic":
            raise LLMProviderError("timeout")
        return "ok"

def test_failover_sequence(monkeypatch):
    svc = Svc(DummyCfg(), DummyLogger(), DummyRouting())
    out = svc.call_llm(
        provider="anthropic", messages=[{"role":"user","content":"hi"}],
        routing_context={"routing_enabled": True}
    )
    assert out == "ok"
    assert svc.seq == [("anthropic","claude-3-5-sonnet"), ("openai","gpt-4o")]
