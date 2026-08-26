"""Orchestrator state and events."""
from __future__ import annotations

from enum import Enum


class AgentState(str, Enum):
    IDLE = "IDLE"
    LISTEN = "LISTEN"
    ASR = "ASR"
    LLM = "LLM"
    TTS = "TTS"


STATE_TRANSITIONS = {
    AgentState.IDLE: AgentState.LISTEN,
    AgentState.LISTEN: AgentState.ASR,
    AgentState.ASR: AgentState.LLM,
    AgentState.LLM: AgentState.TTS,
    AgentState.TTS: AgentState.LISTEN,
}
