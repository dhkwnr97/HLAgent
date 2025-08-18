"""
HLA Teacher Agent Package
=======================

An interactive HLA teacher agent that provides educational information about HLA genetics.
"""

from .agent import HLATeacherAgent
from .agent_types import AgentMode
from .states import HLATeacherStateManager

__all__ = ["HLATeacherAgent", "AgentMode", "HLATeacherStateManager"]
