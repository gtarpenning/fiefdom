# Cupbearer

## Overview 

we are building an application that is a personal assistant.

key features: 
- lives in a versioned vm in fly.io, i think its called a sprite, probably can get away with sqlite or files for the data model.
- single-tenant, this is a project for me
- the personal assistant will be authenticated with: google (email, cal, notes, etc.), whatsapp, slack (personal token), texting (twilio?)
- model agnostic, probably use python and litellm for basic completions. 
- agentic first, main execution is probably a codex agent. 
- can be reached by text or call
- lots of personality, with strict enforcement: I want a business casual assistant. Witty, playful, funny, but on topic and results driven. Most interactions will happen between me, assistant, and friends, it must be fun. 
- because everything lives in the VM, it should be possible for self-improvement, through adding new skills. we want first class skill mangement, possibly versioned.
- memory system. there must be a longterm memory system to capture important tidbits (actually any non-transient information about me), as well as a way of searchign through history to populate a context store.
- the implementatino must be gorgeous. production quality code. high level interfaces and abstractions, easy to read, the actual coding must be staff level and extendable. this might grow with me for years, it has to be bulletproof and easily grow with my needs.
- our north star use case is: Griffin wants to take a trip to new york, I need my cupbearer to chat with my friends to get information about their schedlues, when can they be free etc. call me with a breakdown of the notes, suggestions for places (banter with my friends,ask their preferences recs etc), and help plan an ideal trip. 

