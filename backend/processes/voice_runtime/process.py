from backend.processes.registry import ProcessDef
from backend.services.voice import voice_service


PROCESS = ProcessDef(
    id="voice_runtime",
    name="Voice runtime",
    description="Wake word listener, microphone state, and local voice loop lifecycle.",
    area="voice",
    start=voice_service.enable,
    stop=voice_service.disable,
)
