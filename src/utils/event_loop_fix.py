"""
Event Loop Fix for PydanticAI and Gemini Models
===============================================

This module provides fixes for common event loop issues encountered when using
PydanticAI with Google Gemini models, especially in Jupyter notebooks, async environments,
and when dealing with nested event loops.

Based on official PydanticAI troubleshooting documentation:
https://github.com/pydantic/pydantic-ai/blob/main/docs/troubleshooting.md
"""

import asyncio
import sys
import warnings
from typing import Optional
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def apply_event_loop_fix():
    """
    Apply event loop fixes for PydanticAI and Gemini models.
    
    This function should be called early in the application startup,
    before any async operations or PydanticAI agents are initialized.
    """
    try:
        import nest_asyncio
        nest_asyncio.apply()
        logger.info("Applied nest_asyncio fix for event loop compatibility")
    except ImportError:
        logger.warning("nest_asyncio not available - some async operations may fail")
    
    # Additional event loop fixes for different environments
    _apply_jupyter_fix()
    _apply_threading_fix()
    _apply_streamlit_fix()


def _apply_jupyter_fix():
    """Apply fixes specific to Jupyter notebook environments."""
    try:
        # Check if we're in a Jupyter environment
        if 'ipykernel' in sys.modules:
            logger.info("Detected Jupyter environment - applying additional fixes")
            
            # Suppress Jupyter-related asyncio warnings
            warnings.filterwarnings('ignore', message='There is no current event loop')
            warnings.filterwarnings('ignore', message='coroutine .* was never awaited')
            
    except Exception as e:
        logger.debug(f"Jupyter fix application failed (non-critical): {e}")


def _apply_threading_fix():
    """Apply fixes for threading-related event loop issues."""
    try:
        # Set event loop policy for better thread compatibility
        if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
            # Windows-specific fix
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        elif hasattr(asyncio, 'DefaultEventLoopPolicy'):
            # Unix-like systems
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            
        logger.debug("Applied threading event loop fixes")
        
    except Exception as e:
        logger.debug(f"Threading fix application failed (non-critical): {e}")


def ensure_event_loop() -> asyncio.AbstractEventLoop:
    """
    Ensure there's a running event loop, creating one if necessary.
    
    Returns:
        The current or newly created event loop.
    """
    try:
        loop = asyncio.get_running_loop()
        logger.debug("Found existing event loop")
        return loop
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
            logger.debug("Using existing event loop")
            return loop
        except RuntimeError:
            logger.info("Creating new event loop")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop


def safe_run_async(coro, timeout: Optional[float] = None):
    """
    Safely run an async coroutine, handling event loop issues.
    
    Args:
        coro: The coroutine to run
        timeout: Optional timeout in seconds
        
    Returns:
        The result of the coroutine execution
    """
    try:
        # Try to run in existing event loop
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # If we're already in an async context, we need nest_asyncio
            try:
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(coro)
            except ImportError:
                raise RuntimeError("Cannot run async code in existing event loop without nest_asyncio")
        else:
            return loop.run_until_complete(coro)
            
    except RuntimeError:
        # No event loop running, create a new one
        loop = ensure_event_loop()
        try:
            if timeout:
                return asyncio.wait_for(coro, timeout=timeout)
            else:
                return loop.run_until_complete(coro)
        finally:
            # Clean up if we created the loop
            if not loop.is_running():
                loop.close()


def _apply_streamlit_fix():
    """Apply fixes specific to Streamlit environments."""
    try:
        # Check if we're in a Streamlit environment
        if 'streamlit' in sys.modules:
            logger.info("Detected Streamlit environment - applying additional fixes")
            
            # Streamlit-specific asyncio warnings suppression
            warnings.filterwarnings('ignore', message='There is no current event loop')
            warnings.filterwarnings('ignore', message='coroutine .* was never awaited')
            warnings.filterwarnings('ignore', message='.*is bound to a different event loop')
            
            # Set event loop policy for Streamlit compatibility
            try:
                import threading
                if threading.current_thread() is threading.main_thread():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    logger.debug("Created new event loop for Streamlit main thread")
            except Exception as e:
                logger.debug(f"Streamlit event loop setup failed (non-critical): {e}")
            
    except Exception as e:
        logger.debug(f"Streamlit fix application failed (non-critical): {e}")


def debug_event_loop_state():
    """
    Debug function to check current event loop state.
    Useful for troubleshooting event loop issues.
    """
    try:
        loop = asyncio.get_running_loop()
        logger.info(f"Event loop running: {loop}")
        logger.info(f"Event loop closed: {loop.is_closed()}")
        logger.info(f"Event loop running: {loop.is_running()}")
    except RuntimeError as e:
        logger.info(f"No running event loop: {e}")
        
    try:
        loop = asyncio.get_event_loop()
        logger.info(f"Default event loop: {loop}")
        logger.info(f"Default loop closed: {loop.is_closed()}")
    except RuntimeError as e:
        logger.info(f"No default event loop: {e}")


def reset_agents_for_new_loop():
    """
    Reset any global agent instances to prevent event loop binding issues.
    This should be called when switching between different async contexts.
    """
    try:
        # This function can be called by modules that maintain global agent instances
        logger.info("Resetting global agents for new event loop context")
        
        # Force garbage collection to clean up old event loop references
        import gc
        gc.collect()
        
    except Exception as e:
        logger.debug(f"Agent reset failed (non-critical): {e}")


# Auto-apply fixes when module is imported
apply_event_loop_fix()