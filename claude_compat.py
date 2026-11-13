"""
Claude Compatibility Helpers
File: claude_compat.py
Created: November 13, 2026
Last Updated: November 13, 2026 — Initial implementation

PURPOSE:
    One small place that knows how to talk to both generations of Claude
    models the Swarm may be pointed at:

      * Claude 4.x (claude-sonnet-4-6, claude-opus-4-8): the answer is the
        first block of the reply, and nothing "thinks" unless asked to.
      * Claude 5.x (claude-sonnet-5-5, claude-opus-5-5, claude-haiku-5-5):
        the model thinks before answering by default. That changes three
        things every caller has to get right:
          1. The reply can START with "thinking" blocks, so reading
             response.content[0].text fails. The answer has to be collected
             from the blocks whose type is "text".
          2. Thinking is paid for out of max_tokens. A call that allowed 300
             tokens for a short answer can spend all 300 thinking and return
             nothing. The allowance has to be raised to leave room.
          3. How hard it thinks is set with "effort". Left alone, Sonnet 5.5
             thinks at "high", which is slow and costly for the Swarm's many
             short background calls.

    Every place in the Swarm that calls Claude uses these helpers, so moving
    to a newer or older model is a matter of changing the model name (the
    CLAUDE_SONNET_MODEL / CLAUDE_OPUS_MODEL settings), not the code.

    This file imports nothing from the rest of the Swarm, so anything can
    import it without side effects.

USAGE:
    from claude_compat import claude_request, claude_text

    response = client.messages.create(
        messages=[...],
        **claude_request(model, max_tokens=1000, effort='low'),
    )
    text = claude_text(response)

EFFORT LEVELS USED IN THE SWARM:
    'low'     short, structured background answers (classification, JSON,
              briefings, the public assessment commentary)
    'medium'  the main chat and document work

CHANGELOG:
- November 13, 2026: INITIAL IMPLEMENTATION
  * claude_generation(), claude_request(), claude_text(). Added with the move
    of the Swarm's default models to claude-sonnet-5-5 and claude-opus-5-5.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import re

# Extra room added to max_tokens for the model's own thinking, by effort.
# Only what is actually used is billed; this is a ceiling, not a spend.
THINKING_HEADROOM = {'low': 2000, 'medium': 5000, 'high': 12000, 'xhigh': 32000, 'max': 48000}

_GENERATION = re.compile(r'^claude-[a-z]+-(\d+)')


def claude_generation(model):
    """
    The major version in a model name: 'claude-sonnet-5-5' -> 5,
    'claude-opus-4-8' -> 4. Returns 0 for a name this does not recognise
    (it is then treated like the older models: nothing extra is sent).
    """
    match = _GENERATION.match(str(model or '').strip().lower())
    return int(match.group(1)) if match else 0


def thinks_by_default(model):
    """True for Claude 5.x and later, which think before answering unless told otherwise."""
    return claude_generation(model) >= 5


def claude_request(model, max_tokens, effort='medium'):
    """
    The model-dependent part of a messages.create() call, as keyword arguments.

    For Claude 4.x it is just the model and max_tokens, exactly as before.
    For Claude 5.x it also sets the effort and raises max_tokens so the
    thinking does not eat the room the caller wanted for the answer.
    """
    if not thinks_by_default(model):
        return {'model': model, 'max_tokens': max_tokens}
    if effort not in THINKING_HEADROOM:
        effort = 'medium'
    return {
        'model': model,
        'max_tokens': int(max_tokens) + THINKING_HEADROOM[effort],
        'extra_body': {'output_config': {'effort': effort}},
    }


def claude_text(response):
    """
    The answer text of a reply, whatever blocks came before it.

    Returns '' if the reply holds no text (for example the model declined, or
    ran out of room). Use claude_empty_reason() to say why.
    """
    parts = []
    for block in getattr(response, 'content', None) or []:
        if getattr(block, 'type', None) == 'text':
            parts.append(getattr(block, 'text', '') or '')
    return ''.join(parts)


def claude_empty_reason(response):
    """A plain sentence explaining a reply that has no text."""
    reason = getattr(response, 'stop_reason', None)
    if reason == 'refusal':
        return 'The model declined to answer this request.'
    if reason == 'max_tokens':
        return 'The model ran out of room before it could answer.'
    return f'The model returned no text (stop reason: {reason}).'


# I did no harm and this file is not truncated
