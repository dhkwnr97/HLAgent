"""
Dependencies for Supervisor Agent in PydanticAI multi-agent system.
Manages shared dependencies for agent delegation and orchestration.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
from ..shared.settings import settings
from .prompts import AVAILABLE_AGENT_PROMPTS, AGENT_SELECTION_ANALYSIS_PROMPT


@dataclass  
class SupervisorDependencies:
    """
    Dependencies for Supervisor agent following PydanticAI patterns.
    Manages orchestration and delegation to sub-agents.
    """
    
    # Session Management
    session_id: Optional[str] = None
    current_context: Optional[str] = None
    active_sub_agent: Optional[str] = None
    
    # Agent Management
    available_agents: List[str] = None
    conversation_history: List[Dict[str, Any]] = None
    
    # Delegation Context
    delegation_active: bool = False
    delegation_reason: Optional[str] = None
    pending_handoff: bool = False
    
    # External Communication
    a2a_active: bool = False
    external_context_id: Optional[str] = None
    
    # Sub-agent Dependencies Storage
    hlateacher_deps: Optional[Any] = None
    fileconverter_deps: Optional[Any] = None
    parameterhandler_deps: Optional[Any] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.available_agents is None:
            self.available_agents = ["hlateacher", "fileconverter", "parameterhandler", "genotypephasing", "hlaimputation", "hlafinemapping"]  # Extensible for more agents
        
        if self.conversation_history is None:
            self.conversation_history = []
    
    @classmethod
    def create_default(
        cls,
        session_id: Optional[str] = None,
        external_context_id: Optional[str] = None
    ) -> "SupervisorDependencies":
        """
        Create default supervisor dependencies.
        
        Args:
            session_id: Optional session identifier
            external_context_id: Optional external A2A context ID
            
        Returns:
            Configured SupervisorDependencies instance
        """
        return cls(
            session_id=session_id,
            current_context="supervisor_main",
            active_sub_agent=None,
            available_agents=["hlateacher", "fileconverter", "parameterhandler", "genotypephasing", "hlaimputation", "hlafinemapping"],
            conversation_history=[],
            delegation_active=False,
            delegation_reason=None,
            pending_handoff=False,
            a2a_active=bool(external_context_id),
            external_context_id=external_context_id
        )
    
    def start_delegation(self, agent_name: str, reason: str):
        """Start delegation to a sub-agent."""
        self.active_sub_agent = agent_name
        self.delegation_active = True
        self.delegation_reason = reason
        self.pending_handoff = True
    
    def end_delegation(self):
        """End current delegation and return control to supervisor."""
        self.active_sub_agent = None
        self.delegation_active = False
        self.delegation_reason = None
        self.pending_handoff = False
        # Clear stored sub-agent dependencies
        self.hlateacher_deps = None
        self.fileconverter_deps = None
        self.parameterhandler_deps = None
    
    def add_conversation(self, role: str, content: str, agent_source: str = "supervisor"):
        """Add conversation entry with agent source tracking."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "agent_source": agent_source,
            "timestamp": len(self.conversation_history)
        })
    
    def get_delegation_context(self) -> Dict[str, Any]:
        """Get context for delegation handoff."""
        return {
            "session_id": self.session_id,
            "active_sub_agent": self.active_sub_agent,
            "delegation_reason": self.delegation_reason,
            "conversation_count": len(self.conversation_history),
            "a2a_active": self.a2a_active,
            "external_context_id": self.external_context_id
        }
    
    
    def should_delegate_to_hlateacher(self, query: str) -> tuple[bool, str]:
        """
        Determine if query should be delegated to hlateacher with reason.
        Uses 2-stage approach: keyword-based + LLM-based analysis.
        
        Args:
            query: User query to analyze
            
        Returns:
            Tuple of (should_delegate, reason)
        """
        # First, try the new intelligent agent selection
        best_agent, confidence, reason = self.select_best_agent(query)
        
        if best_agent == "hlateacher" and confidence > 0.7:
            return True, f"LLM-based analysis suggests HLATeacher: {reason}"
        
        # Fallback to keyword-based for hlateacher using existing fast matching
        agent, confidence, reason = self._fast_keyword_matching(query)
        if agent == "hlateacher" and confidence > 0.3:  # Lower threshold for fallback
            return True, f"Keyword match for HLA/genetics/biology: {reason}"
        
        # Check for explicit requests
        if any(phrase in query.lower() for phrase in ["hla teacher", "genetics help", "biology question"]):
            return True, f"User explicitly requested HLA/genetics assistance"
        
        return False, "Query does not appear to require HLA/genetics expertise"
    
    def select_best_agent(self, query: str) -> Tuple[str, float, str]:
        """
        Intelligently select the best agent for a query.
        Uses fast keyword matching first, then LLM analysis for ambiguous cases.
        
        Args:
            query: User query in any language
            
        Returns:
            Tuple of (agent_name, confidence_score, reason)
        """
        # First, try fast keyword matching for obvious cases
        agent, confidence, reason = self._fast_keyword_matching(query)
        
        # If we have a high-confidence keyword match, use it immediately
        if confidence >= 0.8:
            return agent, confidence, f"Fast keyword match: {reason}"
        
        # For ambiguous cases, use expensive LLM analysis
        try:
            # Create analysis prompt for LLM
            agent_descriptions = "\n".join([
                f"**{agent_name}**: {description.strip()}" 
                for agent_name, description in AVAILABLE_AGENT_PROMPTS.items()
            ])
            
            analysis_prompt = AGENT_SELECTION_ANALYSIS_PROMPT.format(
                query=query,
                agent_descriptions=agent_descriptions
            )
            
            result = self._analyze_query_with_llm(analysis_prompt)
            llm_agent, llm_confidence, llm_reason = self._parse_agent_selection_result(result)
            
            # Prefer LLM result if it's confident, otherwise use keyword match
            if llm_confidence > confidence:
                return llm_agent, llm_confidence, f"LLM analysis: {llm_reason}"
            else:
                return agent, confidence, f"Keyword fallback: {reason}"
                
        except Exception as e:
            # Fallback to keyword-based matching
            return agent, confidence, f"LLM failed, using keywords: {reason}"
    
    def _fast_keyword_matching(self, query: str) -> Tuple[str, float, str]:
        """
        Fast keyword-based agent selection for obvious cases.
        
        Args:
            query: User query
            
        Returns:
            Tuple of (agent_name, confidence, reason)
        """
        query_lower = query.lower()
        
        # Enhanced multilingual keyword matching with higher precision
        agent_keywords = {
            "hlateacher": [
                "teacher", "hla teacher", "hla teacher agent", "teacher agent",
                "genetics", "biology", "immunology", "mhc", "what is",
                "explain", "teach", "learn", "education", "question", "knowledge", "know", "don't know",
                "dont know", "tell me", "teach me"
            ],
            "fileconverter": [
                "converter", "file converter", "file converter agent", "file converting agent",
                "file convert agent", "file convert", "convert", "conversion", "format", "file", "transform", 
                "fileconverter", "file modify", "file modification", "format conversion", "file format"
            ],
            "hlaimputation": [
                "hla imputation agent", "imputation agent", "imputation tool", "impute agent",
                "imputation", "impute", "hla imputation", "hlaimputation", "imputing", "hla imputation tool",
                "cookhla", "hlahd", "optitype"
            ],
            "hlafinemapping": [
                "fine mapping agent", "hla fine mapping agent",
                "fine mapping tool", "fine mapping", "hla fine mapping", "hlafinemapping"
            ],
            "parameterhandler": [
                "parameter handler agent", "parameter handler tool", "parameter agent",
                "parameter", "config", "setting", "yaml", "modify", "parameter handler", "parameterhandler"
            ],
            "genotypephasing": [
                "genotype phasing agent", "genotype phasing tool", "phasing agent",
                "genotype phasing", "genotypephasing", 
                "haplotype phasing", "haplotypes phasing", "haplotypes phasing tool",
                "haplotypes phasing agent"
            ]
        }
        
        best_agent = "none"
        best_score = 0.0
        best_reason = "No clear match found"
        
        for agent, keywords in agent_keywords.items():
            # Count exact keyword matches
            exact_matches = sum(1 for keyword in keywords if keyword in query_lower)
            # Calculate score based on exact matches and keyword coverage
            score = exact_matches / len(keywords)
            
            # Boost score for exact agent name matches
            if any(exact_keyword in query_lower for exact_keyword in [f"{agent} agent", f"{agent}"]):
                score += 0.5
            
            if score > best_score:
                best_score = score
                best_agent = agent
                best_reason = f"Found {exact_matches} keyword matches for {agent}"
        
        # Convert score to confidence with more aggressive matching for file converter
        if best_agent == "fileconverter" and best_score > 0:
            confidence = min(0.95, best_score * 5.0)  # More aggressive for file converter
        else:
            confidence = min(0.95, best_score * 3.0) if best_score > 0 else 0.1
        
        return best_agent, confidence, best_reason
    
    def _analyze_query_with_llm(self, prompt: str) -> str:
        """
        Analyze query using actual LLM for intelligent agent selection.
        Supports multiple languages and semantic understanding.
        
        Args:
            prompt: Analysis prompt for LLM
            
        Returns:
            LLM response string
        """
        try:
            # Use the supervisor's LLM for analysis
            from src.agents_pa.shared.universal_providers import get_supervisor_model
            from pydantic_ai import Agent
            
            # Create a temporary agent for analysis
            analysis_agent = Agent(
                model=get_supervisor_model(),
                system_prompt="You are an expert at analyzing user queries and routing them to appropriate specialist agents. You understand multiple languages and can identify the intent and domain expertise required."
            )
            
            # Run synchronous analysis (we'll handle async conversion if needed)
            import asyncio
            
            async def analyze():
                result = await analysis_agent.run(prompt)
                return result.output
            
            # Try to get the current event loop, create one if none exists
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an async context, use create_task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, analyze())
                        return future.result(timeout=10)
                else:
                    return loop.run_until_complete(analyze())
            except RuntimeError:
                # No event loop, create new one
                return asyncio.run(analyze())
                
        except Exception as e:
            # Fallback to simulation if LLM fails
            return self._basic_llm_simulation(prompt)
    
    def _parse_agent_selection_result(self, result: str) -> Tuple[str, float, str]:
        """
        Parse LLM result into structured format.
        
        Args:
            result: LLM response string
            
        Returns:
            Tuple of (agent_name, confidence, reason)
        """
        try:
            lines = result.strip().split('\n')
            agent = "none"
            confidence = 0.0
            reason = "No analysis available"
            
            for line in lines:
                if line.startswith("AGENT:"):
                    agent = line.split(":", 1)[1].strip()
                elif line.startswith("CONFIDENCE:"):
                    confidence = float(line.split(":", 1)[1].strip())
                elif line.startswith("REASON:"):
                    reason = line.split(":", 1)[1].strip()
            
            return agent, confidence, reason
        except Exception:
            return "none", 0.0, "Failed to parse analysis result"
    
    def _fallback_agent_selection(self, query: str) -> Tuple[str, float, str]:
        """
        Fallback agent selection using simple keyword matching.
        
        Args:
            query: User query
            
        Returns:
            Tuple of (agent_name, confidence, reason)
        """
        agent, confidence, reason = self._fast_keyword_matching(query)
        if agent == "hlateacher" and confidence > 0.3:
            return agent, confidence, reason
        
        return "none", 0.0, "No agent match found in fallback"
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get comprehensive session information."""
        return {
            "session_id": self.session_id,
            "current_context": self.current_context,
            "active_sub_agent": self.active_sub_agent,
            "available_agents": self.available_agents,
            "conversation_count": len(self.conversation_history),
            "delegation_active": self.delegation_active,
            "delegation_reason": self.delegation_reason,
            "pending_handoff": self.pending_handoff,
            "a2a_active": self.a2a_active,
            "external_context_id": self.external_context_id
        }